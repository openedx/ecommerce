import logging
from optparse import make_option
from urlparse import urljoin

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from oscar.core.loading import get_model
import requests

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.utils import generate_sku

logger = logging.getLogger(__name__)

Category = get_model('catalogue', 'Category')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


class MigratedCourse(object):
    def __init__(self, course_id):
        # Ensure this value is Unicode to avoid issues with slugify.
        self.course_id = unicode(course_id)

        self.parent_seat = None
        self.child_seats = {}
        self._unsaved_stock_records = {}

        try:
            self.course = Course.objects.get(id=self.course_id)
        except Course.DoesNotExist:
            self.course = Course(id=self.course_id)

    @transaction.atomic
    def save(self):
        self.course.save()

        self.parent_seat.course = self.course
        self.parent_seat.save()
        category = Category.objects.get(name='Seats')
        ProductCategory.objects.get_or_create(category=category, product=self.parent_seat)

        for product in self.child_seats.values():
            product.parent = self.parent_seat
            product.course = self.course
            product.save()

        for seat_type, stock_record in self._unsaved_stock_records.iteritems():
            stock_record.product = self.child_seats[seat_type]
            stock_record.save()

        self._unsaved_stock_records = {}

    def load_from_lms(self):
        """
        Loads course products from the LMS.

        Loaded data is NOT persisted until the save() method is called.
        """
        name, modes = self._retrieve_data_from_lms()
        self.course.name = name
        self._get_products(name, modes)

    def _retrieve_data_from_lms(self):
        """
        Retrieves the course name and modes from the LMS.
        """
        headers = {
            'Accept': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        # Get course name from Course Structure API
        url = urljoin(settings.LMS_URL_ROOT, 'api/course_structure/v0/courses/{}/'.format(self.course_id))
        response = requests.get(url, headers=headers)
        data = response.json()
        logger.debug(data)
        course_name = data['name']

        # TODO Handle non-200 responses and other errors

        # Get modes and pricing from Enrollment API
        url = urljoin(settings.LMS_URL_ROOT, 'api/enrollment/v1/course/{}'.format(self.course_id))
        response = requests.get(url, headers=headers)
        data = response.json()
        logger.debug(data)
        modes = data['course_modes']

        # TODO Handle non-200 responses and other errors

        return course_name, modes

    def _get_product_name(self, course_name, mode):
        name = u'Seat in {course_name} with {certificate_type} certificate'.format(
            course_name=course_name,
            certificate_type=Course.certificate_type_for_mode(mode))

        if Course.is_mode_verified(mode):
            name += u' (and ID verification)'

        return name

    def _get_products(self, course_name, modes):
        """
        Creates course seat products.

        Returns:
            seats (dict):  Mapping of seat types to seat Products
            stock_records (dict):  Mapping of seat types to StockRecords
        """

        course_id = self.course_id

        seats = {}
        stock_records = {}
        slug = u'parent-cs-{}'.format(slugify(course_id))
        partner = Partner.objects.get(code='edx')

        try:
            parent = Product.objects.get(slug=slug)
            logger.info(u'Retrieved parent seat product for [%s] from database.', course_id)
        except Product.DoesNotExist:
            product_class = ProductClass.objects.get(slug='seat')
            parent = Product(slug=slug, is_discountable=True, structure=Product.PARENT, product_class=product_class)
            logger.info(u'Parent seat product for [%s] does not exist. Instantiated a new instance.', course_id)

        parent.title = u'Seat in {}'.format(course_name)
        parent.attr.course_key = course_id

        # Create the child products
        for mode in modes:
            seat_type = mode['slug']
            slug = u'child-cs-{}-{}'.format(seat_type, slugify(course_id))
            try:
                seat = Product.objects.get(slug=slug)
                logger.info(u'Retrieved [%s] course seat child product for [%s] from database.', seat_type, course_id)
            except Product.DoesNotExist:
                seat = Product(slug=slug)
                logger.info(u'[%s] course seat product for [%s] does not exist. Instantiated a new instance.',
                            seat_type, course_id)

            seat.parent = parent
            seat.is_discountable = True
            seat.structure = Product.CHILD
            seat.title = self._get_product_name(course_name, seat_type)
            seat.attr.certificate_type = seat_type
            seat.attr.course_key = course_id
            seat.attr.id_verification_required = Course.is_mode_verified(seat_type)

            seats[seat_type] = seat

            try:
                stock_record = StockRecord.objects.get(product=seat, partner=partner)
                logger.info(u'Retrieved [%s] course seat child product stock record for [%s] from database.',
                            seat_type, course_id)
            except StockRecord.DoesNotExist:
                partner_sku = generate_sku(seat)
                stock_record = StockRecord(product=seat, partner=partner, partner_sku=partner_sku)
                logger.info(
                    u'[%s] course seat product stock record for [%s] does not exist. Instantiated a new instance.',
                    seat_type, course_id)

            stock_record.price_excl_tax = mode['min_price']
            stock_record.price_currency = 'USD'

            stock_records[seat_type] = stock_record

        self.parent_seat = parent
        self.child_seats = seats
        self._unsaved_stock_records = stock_records


class Command(BaseCommand):
    help = 'Migrate course modes and pricing from LMS to Oscar.'

    option_list = BaseCommand.option_list + (
        make_option('--commit',
                    action='store_true',
                    dest='commit',
                    default=False,
                    help='Save the migrated data to the database. If this is not set, '
                         'migrated data will NOT be saved to the database.'),
    )

    def handle(self, *args, **options):
        course_ids = args

        for course_id in course_ids:
            course_id = unicode(course_id)
            try:
                migrated_course = MigratedCourse(course_id)
                migrated_course.load_from_lms()

                course = migrated_course.course
                msg = 'Retrieved info for {0} ({1}):\n'.format(course.id, course.name)

                for seat_type, seat in migrated_course.child_seats.iteritems():
                    stock_record = migrated_course._unsaved_stock_records[seat_type]  # pylint: disable=protected-access
                    data = (seat_type, seat.attr.id_verification_required,
                            '{0} {1}'.format(stock_record.price_currency, stock_record.price_excl_tax),
                            stock_record.partner_sku)
                    msg += '\t{}\n'.format(data)

                logger.info(msg)

                if options.get('commit', False):
                    migrated_course.save()
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to migrate [%s]!', course_id)
