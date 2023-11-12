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
from oscar.core.loading import get_class

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.courses.constants import CertificateType
from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_detail, get_course_run_detail
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.iap.api.v1.utils import create_ios_product
from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.extensions.iap.processors.ios_iap import IOSIAP
from ecommerce.extensions.iap.utils import create_child_products_for_mobile

Dispatcher = get_class('communication.utils', 'Dispatcher')
logger = logging.getLogger(__name__)

ANDROID_SKU_KEY = 'android_sku'
COURSE_KEY = 'course_key'
IOS_SKU_KEY = 'ios_sku'


class CourseRunFetchException(Exception):
    pass


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
        failed_ios_products = []
        expired_courses_keys = []
        all_course_runs_processed = []
        failed_course_runs = []
        new_seats_created = []
        default_site = Site.objects.filter(id=settings.SITE_ID).first()
        batch_counter = 0

        # Fetch products which expired in the last month and had mobile skus.
        expired_products = Product.objects.filter(
            attribute_values__attribute__name="certificate_type",
            attribute_values__value_text=CertificateType.VERIFIED,
            parent__product_class__name=SEAT_PRODUCT_CLASS_NAME,
            stockrecords__partner_sku__icontains="mobile",
            expires__lt=now(),
            expires__gt=now() - timedelta(days=30)
        )

        # Fetch courses for these products
        expired_courses = Course.objects.filter(products__in=expired_products).distinct()
        if expired_courses:
            expired_courses_keys = list(expired_courses.values_list('id', flat=True))

        for expired_course in expired_courses:
            try:
                all_course_run_keys = self._get_related_course_run_keys(expired_course, default_site)
            except CourseRunFetchException:
                # Logging of exception is already done inside _get_related_course_run_keys
                continue  # pragma: no cover

            all_course_runs = Course.objects.filter(id__in=all_course_run_keys)
            for course_run in all_course_runs:
                all_course_runs_processed.append(course_run.id)
                parent_product = self._get_parent_product_to_create_mobile_skus_for(course_run)

                try:
                    mobile_products = create_child_products_for_mobile(parent_product)
                    if not mobile_products:
                        raise Exception
                except Exception:  # pylint: disable=broad-except
                    failed_course_runs.append(course_run.id)
                    continue

                android_sku = list(filter(lambda sku: 'android' in sku.partner_sku, mobile_products))[0].partner_sku
                ios_product = list(filter(lambda sku: 'ios' in sku.partner_sku, mobile_products))[0]
                ios_sku = ios_product.partner_sku
                new_seats_created.append("{},{},{}".format(ios_sku, android_sku, course_run.id))

                error_message = self._create_ios_product(course_run, ios_product, default_site)
                if error_message:
                    failed_ios_products.append(error_message)
                course_run.publish_to_lms()

            batch_counter += 1
            if batch_counter >= batch_size:
                time.sleep(sleep_time)
                batch_counter = 0
        self._send_email_about_expired_courses(expired_courses_keys, all_course_runs_processed,
                                               failed_course_runs, new_seats_created, failed_ios_products)

    def _get_related_course_run_keys(self, course, default_site):
        """
        Get parent course key from discovery for the current course run.
        Get all course run keys for parent course from discovery. Then filter those
        courses/course runs on Ecommerce using Course.verification_deadline and
        Product.expires to determine mobile products to create course runs for.
        """

        course_run_detail_response = get_course_run_detail(default_site, course.id)
        try:
            parent_course_key = course_run_detail_response.get('course')
        except AttributeError as err:
            message = "Error while fetching parent course for {} from discovery".format(course.id)
            logger.error(message)
            raise CourseRunFetchException from err

        parent_course = get_course_detail(default_site, parent_course_key)
        try:
            all_course_run_keys = parent_course.get('course_run_keys')
        except AttributeError as err:
            message = "Error while fetching course runs for {} from discovery".format(parent_course_key)
            logger.error(message)
            raise CourseRunFetchException from err

        return all_course_run_keys

    def _get_parent_product_to_create_mobile_skus_for(self, course):
        """
        From courses, filter the products that:
        - Have expiry date in the future
        - Have verified attribute set
        - Have web skus created for them
        - Do not have mobile skus created for them yet
        """
        product_to_create_mobile_skus_for = Product.objects.filter(
            ~Q(children__stockrecords__partner_sku__icontains="mobile"),
            structure=Product.PARENT,
            children__stockrecords__isnull=False,
            children__attribute_values__attribute__name="certificate_type",
            children__attribute_values__value_text=CertificateType.VERIFIED,
            product_class__name=SEAT_PRODUCT_CLASS_NAME,
            children__expires__gt=now(),
            course=course,
        ).first()
        return product_to_create_mobile_skus_for

    def _create_ios_product(self, course, ios_product, site):
        # create ios product on appstore
        partner_short_code = site.siteconfiguration.partner.short_code
        configuration = settings.PAYMENT_PROCESSOR_CONFIG[partner_short_code.lower()][IOSIAP.NAME.lower()]
        course_data = {
            'price': ios_product.price,
            'name': course.name,
            'key': course.id,
        }
        error_message = create_ios_product(course_data, ios_product, configuration)
        return error_message

    def _send_email_about_expired_courses(self, expired_courses_keys, all_course_runs_processed,
                                          failed_course_runs, new_seats_created, failed_ios_products):
        """
        Send email to IAPProcessorConfiguration.mobile_team_email with SKUS for
        expired mobile courses.
        """
        email_body = self._get_email_contents(
            expired_courses_keys, all_course_runs_processed, failed_course_runs, new_seats_created, failed_ios_products)
        recipient = IAPProcessorConfiguration.get_solo().mobile_team_email
        if not recipient:
            message = "Couldn't mail mobile team for expired courses with SKUS. " \
                "No email was specified for mobile team in configurations.\n " \
                "Email contents: {}".format(email_body)
            logger.info(message)
            return

        messages = {
            'subject': 'Expired Courses with mobile SKUS alert',
            'body': email_body,
            'html': None,
        }
        Dispatcher().dispatch_direct_messages(recipient, messages)
        logger.info("Sent Expired Courses alert email to mobile team.")

    def _get_email_contents(self, expired_courses_keys, all_course_runs_processed,
                            failed_course_runs, new_seats_created, failed_ios_products):
        body = "\nExpired Courses:\n" + '\n'.join(expired_courses_keys)
        body += "\n\nNew course runs processed:\n" + '\n'.join(all_course_runs_processed)
        body += "\n\nFailed course runs:\n" + '\n'.join(failed_course_runs)
        body += "\n\nSeats created:\n" + '\n'.join(new_seats_created)
        body += "\n\nFailed iOS products:\n" + '\n'.join(failed_ios_products)
        return body
