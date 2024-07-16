""" Test utilities for iap management commands """
from decimal import Decimal

from django.utils.timezone import now, timedelta

from ecommerce.courses.constants import CertificateType
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.partner.models import StockRecord
from ecommerce.tests.testcases import TransactionTestCase

ANDROID_SKU_PREFIX = 'android'
IOS_SKU_PREFIX = 'ios'


class BaseIAPManagementCommandTests(DiscoveryTestMixin, TransactionTestCase):
    """
    Base class for iap management commands.
    """
    def create_course_and_seats(self, create_mobile_seats=False, expired_in_past=False, create_web_seat=True):
        """
        Create the specified number of courses with audit and verified seats. Create mobile seats
        if specified.
        """
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('audit', False, 0)
        if create_web_seat:
            verified_seat = course.create_or_update_seat('verified', True, Decimal(10.0))
            verified_seat.title = (
                f'Seat in {course.name} with verified certificate (and ID verification)'
            )
            expires = now() - timedelta(days=10) if expired_in_past else now() + timedelta(days=10)
            verified_seat.expires = expires
            verified_seat.save()
            if create_mobile_seats:
                self.create_mobile_seat_for_course(course, ANDROID_SKU_PREFIX)
                self.create_mobile_seat_for_course(course, IOS_SKU_PREFIX)

        return course

    def create_mobile_seat_for_course(self, course, sku_prefix):
        """ Create a mobile seat for a course given the sku_prefix """
        web_seat = self.get_web_seat_for_course(course)
        web_stock_record = web_seat.stockrecords.first()
        mobile_seat = Product.objects.create(
            course=course,
            parent=web_seat.parent,
            structure=web_seat.structure,
            expires=web_seat.expires,
            is_public=web_seat.is_public,
            title="{} {}".format(sku_prefix.capitalize(), web_seat.title.lower())
        )

        mobile_seat.attr.certificate_type = web_seat.attr.certificate_type
        mobile_seat.attr.course_key = web_seat.attr.course_key
        mobile_seat.attr.id_verification_required = web_seat.attr.id_verification_required
        mobile_seat.attr.save()

        StockRecord.objects.create(
            partner=web_stock_record.partner,
            product=mobile_seat,
            partner_sku="mobile.{}.{}".format(sku_prefix.lower(), web_stock_record.partner_sku.lower()),
            price_currency=web_stock_record.price_currency,
            price_excl_tax=100
        )
        return mobile_seat

    @staticmethod
    def get_web_seat_for_course(course):
        """ Get the default seat created for web for a course """
        return Product.objects.filter(
            parent__isnull=False,
            course=course,
            attributes__name="id_verification_required",
            parent__product_class__name="Seat"
        ).exclude(stockrecords__partner_sku__icontains="mobile").first()

    @staticmethod
    def get_mobile_seats_for_course(course):
        """ Get mobile seats created for a course """
        return Product.objects.filter(
            parent__isnull=False,
            course=course,
            parent__product_class__name="Seat",
            attribute_values__attribute__name="certificate_type",
            attribute_values__value_text=CertificateType.VERIFIED,
            stockrecords__isnull=False,
            stockrecords__partner_sku__icontains="mobile",
        )
