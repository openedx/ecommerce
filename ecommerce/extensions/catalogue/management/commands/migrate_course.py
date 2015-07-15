from __future__ import unicode_literals
import logging
from optparse import make_option

import dateutil.parser
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
        # Do NOT publish back to LMS until all data has been saved.
        self.course.save(publish=False)

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

        # Publish to LMS
        self.course.publish_to_lms()

    def load_from_lms(self, access_token):
        """
        Loads course products from the LMS.

        Loaded data is NOT persisted until the save() method is called.
        """
        name, modes = self._retrieve_data_from_lms(access_token)
        self.course.name = name
        self._get_products(name, modes)

    def _build_lms_url(self, path):
        # We avoid using urljoin here because it URL-encodes the path, and some LMS APIs
        # are not capable of decoding these values.
        host = settings.LMS_URL_ROOT.strip('/')
        return '{host}/{path}'.format(host=host, path=path)

    def _retrieve_data_from_lms(self, access_token):
        """
        Retrieves the course name and modes from the LMS.
        """
        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }

        # Get course name from Course Structure API
        url = self._build_lms_url('api/course_structure/v0/courses/{}/'.format(self.course_id))
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception('Unable to retrieve course name: [{status}] - {body}'.format(status=response.status_code,
                                                                                         body=response.content))

        data = response.json()
        logger.debug(data)
        course_name = data['name']

        # Get modes and pricing from Enrollment API
        url = self._build_lms_url('api/enrollment/v1/course/{}'.format(self.course_id))
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception('Unable to retrieve course modes: [{status}] - {body}'.format(status=response.status_code,
                                                                                          body=response.content))

        data = response.json()
        logger.debug(data)
        modes = data['course_modes']

        return course_name, modes

    def _get_product_name(self, course_name, mode):
        name = 'Seat in {course_name} with {certificate_type} certificate'.format(
            course_name=course_name,
            certificate_type=Course.certificate_type_for_mode(mode))

        if Course.is_mode_verified(mode):
            name += ' (and ID verification)'

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
        slug = 'parent-cs-{}'.format(slugify(course_id))
        partner = Partner.objects.get(code='edx')

        try:
            parent = Product.objects.get(slug=slug)
            logger.info('Retrieved parent seat product for [%s] from database.', course_id)
        except Product.DoesNotExist:
            product_class = ProductClass.objects.get(slug='seat')
            parent = Product(slug=slug, is_discountable=True, structure=Product.PARENT, product_class=product_class)
            logger.info('Parent seat product for [%s] does not exist. Instantiated a new instance.', course_id)

        parent.title = 'Seat in {}'.format(course_name)
        parent.attr.course_key = course_id

        # Create the child products
        for mode in modes:
            seat_type = mode['slug']
            slug = 'child-cs-{}-{}'.format(seat_type, slugify(course_id))
            try:
                seat = Product.objects.get(slug=slug)
                logger.info('Retrieved [%s] course seat child product for [%s] from database.', seat_type, course_id)
            except Product.DoesNotExist:
                seat = Product(slug=slug)
                logger.info('[%s] course seat product for [%s] does not exist. Instantiated a new instance.',
                            seat_type, course_id)

            seat.parent = parent
            seat.is_discountable = True
            seat.structure = Product.CHILD
            seat.title = self._get_product_name(course_name, seat_type)
            expires = mode.get('expiration_datetime')
            seat.expires = dateutil.parser.parse(expires) if expires else None
            seat.attr.certificate_type = seat_type
            seat.attr.course_key = course_id
            seat.attr.id_verification_required = Course.is_mode_verified(seat_type)

            seats[seat_type] = seat

            try:
                stock_record = StockRecord.objects.get(product=seat, partner=partner)
                logger.info('Retrieved [%s] course seat child product stock record for [%s] from database.',
                            seat_type, course_id)
            except StockRecord.DoesNotExist:
                partner_sku = generate_sku(seat)
                stock_record = StockRecord(product=seat, partner=partner, partner_sku=partner_sku)
                logger.info(
                    '[%s] course seat product stock record for [%s] does not exist. Instantiated a new instance.',
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
        make_option('--access_token',
                    action='store',
                    dest='access_token',
                    default=None,
                    help='OAuth2 access token used to authenticate against the LMS APIs.'),
        make_option('--commit',
                    action='store_true',
                    dest='commit',
                    default=False,
                    help='Save the migrated data to the database. If this is not set, '
                         'migrated data will NOT be saved to the database.'),
    )

    def handle(self, *args, **options):
        course_ids = args
        access_token = options.get('access_token')
        if not access_token:
            logger.error('Courses cannot be migrated if no access token is supplied.')
            return

        for course_id in course_ids:
            course_id = unicode(course_id)
            try:
                migrated_course = MigratedCourse(course_id)
                migrated_course.load_from_lms(access_token)

                course = migrated_course.course
                msg = 'Retrieved info for {0} ({1}):\n'.format(course.id, course.name)

                for seat_type, seat in migrated_course.child_seats.iteritems():
                    stock_record = migrated_course._unsaved_stock_records[seat_type]  # pylint: disable=protected-access
                    data = (seat_type, seat.attr.id_verification_required,
                            '{0} {1}'.format(stock_record.price_currency, stock_record.price_excl_tax),
                            stock_record.partner_sku, seat.slug, seat.expires)
                    msg += '\t{}\n'.format(data)

                logger.info(msg)

                if options.get('commit', False):
                    migrated_course.save()
                    logger.info('Course [%s] was saved to the database.', migrated_course.course.id)
                else:
                    logger.info('Course [%s] was NOT saved to the database.', migrated_course.course.id)
            except Exception:  # pylint: disable=broad-except
                logger.exception('Failed to migrate [%s]!', course_id)
