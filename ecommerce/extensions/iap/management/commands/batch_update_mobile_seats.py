"""
This command fetches new course runs for mobile supported courses and creates seats/SKUS for them.
"""
import logging
import time

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.db.models import Q
from django.utils.timezone import now, timedelta

from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_detail, get_course_run_detail
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.extensions.partner.models import StockRecord
from oscar.core.loading import get_class

ANDROID_SKU_PREFIX = 'android'
IOS_SKU_PREFIX = 'ios'
Dispatcher = get_class('communication.utils', 'Dispatcher')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Create Seats/SKUS for new course runs of courses that have mobile payments enabled and
    have expired.
    """

    help = 'Create Seats/SKUS for all new course runs of mobile supported courses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Maximum number of seats to update in one batch')
        parser.add_argument(
            '--sleep-time',
            type=int,
            default=10,
            help='Sleep time in seconds between update of batches')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        sleep_time = options['sleep_time']
        default_site = Site.objects.filter(id=settings.SITE_ID).first()
        batch_counter = 0

        # Fetch products which expired in the last month and had mobile skus.
        expired_products = Product.objects.filter(
            attributes__name="id_verification_required",
            parent__product_class__name="Seat",
            stockrecords__partner_sku__icontains="mobile",
            expires__lt=now(),
            expires__gt=now() - timedelta(days=30)
        )

        # Fetch courses for these products
        expired_courses = Course.objects.filter(products__in=expired_products)
        self._send_email_about_expired_courses(expired_courses=expired_courses)
        for expired_course in expired_courses:
            # Get parent course key from discovery for the current course run
            course_run_detail_response = get_course_run_detail(default_site, expired_course.id)
            parent_course_key = course_run_detail_response.get('course')

            # Get all course run keys for parent course from discovery. Then filter those
            # courses/course runs on Ecommerce using Course.verification_deadline and
            # Product.expires to determine products to create course runs for.
            parent_course_response = get_course_detail(default_site, parent_course_key)
            all_course_run_keys_for_parent_course = parent_course_response.get('course_run_keys')

            all_course_runs_for_parent_course = Course.objects.filter(id__in=all_course_run_keys_for_parent_course)
            parent_products = self._get_parent_products_to_create_mobile_skus_for(all_course_runs_for_parent_course)
            for parent_product in parent_products:
                self._create_child_products_for_mobile(parent_product)

            expired_course.publish_to_lms()
            batch_counter += 1
            if batch_counter >= batch_size:
                time.sleep(sleep_time)
                batch_counter = 0

    def _get_parent_products_to_create_mobile_skus_for(self, courses):
        """
        From courses, filter the products that:
        - Have expiry date in the future
        - Have verified attribute set
        - Have web skus created for them
        - Do not have mobile skus created for them yet
        """
        products_to_create_mobile_skus_for = Product.objects.filter(
            ~Q(children__stockrecords__partner_sku__icontains="mobile"),
            children__stockrecords__isnull=False,
            children__attributes__name="id_verification_required",
            product_class__name="Seat",
            children__expires__gt=now(),
            course__in=courses,
        )
        return products_to_create_mobile_skus_for

    def _create_child_products_for_mobile(self, product):
        """
        Create child products/seats for IOS and Android.
        Child product is also called a variant in the UI
        """
        existing_web_seat = Product.objects.filter(
            ~Q(stockrecords__partner_sku__icontains="mobile"),
            parent=product,
            attributes__name="id_verification_required",
            parent__product_class__name="Seat",
        ).first()
        if existing_web_seat:
            self._create_mobile_seat(ANDROID_SKU_PREFIX, existing_web_seat)
            self._create_mobile_seat(IOS_SKU_PREFIX, existing_web_seat)

    def _create_mobile_seat(self, sku_prefix, existing_web_seat):
        """
        Create a mobile seat, attributes and stock records matching the given existing_web_seat
        in the same Parent Product.
        """
        try:
            new_mobile_seat = Product.objects.get(
                title="{} {}".format(sku_prefix.capitalize(), existing_web_seat.title.lower()),
                course=existing_web_seat.course,
                parent=existing_web_seat.parent
            )
        except Product.DoesNotExist:
            new_mobile_seat = Product()
            new_mobile_seat.title = "{} {}".format(sku_prefix.capitalize(), existing_web_seat.title.lower())
            new_mobile_seat.course = existing_web_seat.course
            new_mobile_seat.parent = existing_web_seat.parent
        new_mobile_seat.structure = existing_web_seat.structure
        new_mobile_seat.product_class = existing_web_seat.product_class
        new_mobile_seat.expires = existing_web_seat.expires
        new_mobile_seat.is_public = existing_web_seat.is_public
        new_mobile_seat.save()

        # Set seat attributes
        new_mobile_seat.attr.certificate_type = existing_web_seat.attr.certificate_type
        new_mobile_seat.attr.course_key = existing_web_seat.attr.course_key
        new_mobile_seat.attr.id_verification_required = existing_web_seat.attr.id_verification_required
        new_mobile_seat.attr.save()

        # Create stock records
        existing_stock_record = existing_web_seat.stockrecords.first()
        try:
            mobile_stock_record = StockRecord.objects.get(
                product=new_mobile_seat, partner=existing_stock_record.partner)
        except StockRecord.DoesNotExist:
            partner_sku = 'mobile.{}.{}'.format(sku_prefix.lower(), existing_stock_record.partner_sku.lower())
            mobile_stock_record = StockRecord(
                product=new_mobile_seat, partner=existing_stock_record.partner, partner_sku=partner_sku)

        mobile_stock_record.price_currency = existing_stock_record.price_currency
        mobile_stock_record.price_excl_tax = existing_stock_record.price_excl_tax
        mobile_stock_record.price_retail = existing_stock_record.price_retail
        mobile_stock_record.cost_price = existing_stock_record.cost_price
        mobile_stock_record.save()

    def _send_email_about_expired_courses(self, expired_courses):
        """
        Send email to IAPProcessorConfiguration.mobile_team_email with SKUS for
        expired mobile courses.
        """
        recipient = IAPProcessorConfiguration.get_solo().mobile_team_email
        expired_courses_keys = list(expired_courses.values_list('id', flat=True))
        messages = {
            'subject': 'Expired Courses with mobile SKUS alert',
            'body': "\n".join(expired_courses_keys),
            'html': None,
        }
        Dispatcher().dispatch_direct_messages(recipient, messages)
        logger.info("Sent Expired Courses alert email to mobile team.")
