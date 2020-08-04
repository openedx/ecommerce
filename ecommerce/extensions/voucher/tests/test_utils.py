# -*- coding: utf-8 -*-


import uuid

import ddt
import httpretty
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import override_settings
from django.utils.translation import ugettext_lazy as _
from factory.fuzzy import FuzzyText
from oscar.templatetags.currency_filters import currency
from oscar.test.factories import (
    BenefitFactory,
    ConditionalOfferFactory,
    OrderFactory,
    OrderLineFactory,
    RangeFactory,
    VoucherFactory,
    datetime,
    get_model
)

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.api import exceptions
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.fulfillment.modules import CouponFulfillmentModule
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.offer.models import OFFER_PRIORITY_VOUCHER
from ecommerce.extensions.test.factories import create_order, prepare_voucher
from ecommerce.extensions.voucher.utils import (
    create_vouchers,
    generate_coupon_report,
    get_voucher_and_products_from_code,
    get_voucher_discount_info,
    update_voucher_offer
)
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
CouponVouchers = get_model('voucher', 'CouponVouchers')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

VOUCHER_CODE = "XMASC0DE"
VOUCHER_CODE_LENGTH = 1


@ddt.ddt
@httpretty.activate
class UtilTests(CouponMixin, DiscoveryMockMixin, DiscoveryTestMixin, LmsApiMockMixin, TestCase):
    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(UtilTests, self).setUp()

        self.user = self.create_user(full_name="Tešt Ušer", is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(id='course-v1:test-org+course+run', partner=self.partner)
        self.verified_seat = self.course.create_or_update_seat('verified', False, 100)

        self.catalog = Catalog.objects.create(partner=self.partner)

        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()
        self.seat_price = self.stock_record.price_excl_tax
        self.catalog.stock_records.add(self.stock_record)

        self.coupon = self.create_coupon(
            title='Tešt product',
            catalog=self.catalog,
            note='Tešt note',
            quantity=1,
            max_uses=1,
            voucher_type=Voucher.MULTI_USE
        )
        self.coupon.history.all().update(history_user=self.user)
        self.coupon_vouchers = CouponVouchers.objects.filter(coupon=self.coupon)

        self.entitlement = create_or_update_course_entitlement(
            'verified', 100, self.partner, 'foo-bar', 'Foo Bar Entitlement'
        )
        self.entitlement_stock_record = StockRecord.objects.filter(product=self.entitlement).first()
        self.entitlement_catalog = Catalog.objects.create(partner=self.partner)
        self.entitlement_catalog.stock_records.add(self.entitlement_stock_record)
        self.entitlement_coupon = self.create_coupon(
            title='Tešt Entitlement product',
            catalog=self.entitlement_catalog,
            note='Tešt Entitlement note',
            quantity=1,
            max_uses=1,
            voucher_type=Voucher.MULTI_USE
        )
        self.entitlement_coupon_vouchers = CouponVouchers.objects.filter(coupon=self.entitlement_coupon)

        self.partner_sku = 'test_sku'

        self.data = {
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100.00,
            'catalog': self.catalog,
            'coupon': self.coupon,
            'end_datetime': datetime.datetime.now() + datetime.timedelta(days=1),
            'enterprise_customer': None,
            'enterprise_customer_catalog': None,
            'name': "Test voucher",
            'quantity': 10,
            'start_datetime': datetime.datetime.now() - datetime.timedelta(days=1),
            'voucher_type': Voucher.SINGLE_USE
        }

    def create_benefits(self):
        """
        Create all Benefit permutations
            - Benefit type: Percentage, Benefit value: 100%
            - Benefit type: Percentage, Benefit value: 50%
            - Benefit type: Value, Benefit value: seat price
            - Benefit type: Value, Benefit value: half the seat price
        """
        _range = RangeFactory(products=[self.verified_seat, ])

        benefit_percentage_all = BenefitFactory(type=Benefit.PERCENTAGE, range=_range, value=100.00)
        benefit_percentage_half = BenefitFactory(type=Benefit.PERCENTAGE, range=_range, value=50.00)
        benefit_value_all = BenefitFactory(type=Benefit.FIXED, range=_range, value=self.seat_price)
        benefit_value_half = BenefitFactory(type=Benefit.FIXED, range=_range, value=self.seat_price / 2)

        return [benefit_percentage_all, benefit_percentage_half, benefit_value_all, benefit_value_half]

    def setup_coupons_for_report(self):
        """ Create specific coupons to test report generation """
        self.data.update({
            'benefit_value': 50.00,
            'code': VOUCHER_CODE,
            'max_uses': 1,
            'name': 'Discount',
            'quantity': 1,
            'voucher_type': Voucher.ONCE_PER_CUSTOMER
        })
        vouchers = create_vouchers(**self.data)
        self.coupon_vouchers.first().vouchers.add(*vouchers)

        del self.data['code']
        del self.data['max_uses']

        self.data.update({
            'benefit_type': Benefit.FIXED,
            'benefit_value': 100.00,
            'voucher_type': Voucher.SINGLE_USE
        })
        vouchers = create_vouchers(**self.data)
        self.coupon_vouchers.first().vouchers.add(*vouchers)

    def create_catalog_coupon(
            self,
            coupon_title='Query coupon',
            quantity=1,
            catalog_query='*:*',
            course_seat_types='verified'
    ):
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url)
        return self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            catalog_query=catalog_query,
            course_seat_types=course_seat_types
        )

    def create_course_catalog_coupon(self, coupon_title, quantity, course_catalog, course_seat_types):
        return self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            course_catalog=course_catalog,
            course_seat_types=course_seat_types,
        )

    def use_voucher(self, order_num, voucher, user, add_entitlement=False, product=None):
        """
        Mark voucher as used by provided users

        Args:
            order_num (string): Order number
            voucher (Voucher): voucher to be marked as used
            users (list): list of users
        """
        order = OrderFactory(number=order_num)
        if add_entitlement:
            order_line = OrderLineFactory(product=self.entitlement, partner_sku=self.partner_sku)
            order.lines.add(order_line)
        product = product if product else self.verified_seat
        order_line = OrderLineFactory(product=product, partner_sku=self.partner_sku)
        order.lines.add(order_line)
        voucher.record_usage(order, user)
        voucher.offers.first().record_usage(discount={'freq': 1, 'discount': 1})

    def validate_report_of_redeemed_vouchers(self, row, username, order_num):
        """ Helper method for validating coupon report data for when a coupon was redeemed. """
        self.assertEqual(row['Status'], _('Redeemed'))
        self.assertEqual(row['Redeemed By Username'], username)
        self.assertEqual(row['Order Number'], order_num)

    def test_create_vouchers(self):
        """
        Test voucher creation
        """
        email_domains = 'edx.org,example.com'
        self.data.update({
            'email_domains': email_domains,
            'name': 'Tešt voučher',
            'site': self.site
        })
        vouchers = create_vouchers(**self.data)

        self.assertEqual(len(vouchers), 10)

        voucher = vouchers[0]
        voucher_offer = voucher.offers.first()
        coupon_voucher = CouponVouchers.objects.get(coupon=self.coupon)
        coupon_voucher.vouchers.add(*vouchers)

        self.assertEqual(voucher_offer.benefit.type, Benefit.PERCENTAGE)
        self.assertEqual(voucher_offer.benefit.value, 100.00)
        self.assertEqual(voucher_offer.benefit.range.catalog, self.catalog)
        self.assertEqual(voucher_offer.email_domains, email_domains)
        self.assertEqual(voucher_offer.priority, OFFER_PRIORITY_VOUCHER)
        self.assertEqual(voucher_offer.partner, self.partner)
        self.assertEqual(len(coupon_voucher.vouchers.all()), 11)
        self.assertEqual(voucher.end_datetime, self.data['end_datetime'])
        self.assertEqual(voucher.start_datetime, self.data['start_datetime'])
        self.assertEqual(voucher.usage, Voucher.SINGLE_USE)

    def test_create_voucher_with_long_name(self):
        self.data.update({
            'name': (
                'This Is A Really Really Really Really Really Really Long '
                'Voucher Name That Needs To Be Trimmed To Fit Into The Name Column Of The DB'
            )
        })
        trimmed = (
            'This Is A Really Really Really Really Really Really Long '
            'Voucher Name That Needs To Be Trimmed To Fit Into The Name Column Of Th'
        )
        vouchers = create_vouchers(**self.data)
        voucher = vouchers[0]
        self.assertEqual(voucher.name, trimmed)

    @ddt.data(
        {'end_datetime': ''},
        {'end_datetime': 3},
        {'end_datetime': 'nonumbers'},
        {'start_datetime': ''},
        {'start_datetime': 3},
        {'start_datetime': 'nonumbers'},
    )
    def test_create_vouchers_with_incorrect_datetime_value(self, data):
        """ Test calling create vouchers with incorrect start/end datetime value raises exception. """
        self.data.update(data)
        with self.assertRaises(ValidationError):
            create_vouchers(**self.data)

    @override_settings(VOUCHER_CODE_LENGTH=VOUCHER_CODE_LENGTH)
    def test_regenerate_voucher_code(self):
        """
        Test that voucher code will be regenerated if it already exists
        """
        self.data.update({
            'benefit_value': 90.00,
            'quantity': 1
        })
        for code in 'BCDFGHJKL':
            self.data['code'] = code
            create_vouchers(**self.data)

        del self.data['code']
        for __ in range(20):
            voucher = create_vouchers(**self.data)
            self.assertTrue(Voucher.objects.filter(code__iexact=voucher[0].code).exists())

    @override_settings(VOUCHER_CODE_LENGTH=0)
    def test_nonpositive_voucher_code_length(self):
        """
        Test that setting a voucher code length to a nonpositive integer value
        raises a ValueError
        """
        with self.assertRaises(ValueError):
            create_vouchers(**self.data)

    def test_create_discount_coupon(self):
        """
        Test discount voucher creation with specified code
        """
        self.data.update({
            'benefit_value': 25.00,
            'code': VOUCHER_CODE,
            'quantity': 1
        })
        discount_vouchers = create_vouchers(**self.data)

        self.assertEqual(len(discount_vouchers), 1)
        self.assertEqual(discount_vouchers[0].code, VOUCHER_CODE)

        with self.assertRaises(IntegrityError):
            create_vouchers(**self.data)

    def test_create_course_catalog_coupon(self):
        """
        Test course catalog coupon voucher creation with specified catalog id.
        """
        coupon_title = 'Course catalog coupon'
        quantity = 1
        course_catalog = 1

        course_catalog_coupon = self.create_course_catalog_coupon(
            coupon_title=coupon_title,
            quantity=quantity,
            course_catalog=course_catalog,
            course_seat_types='verified',
        )
        self.assertEqual(course_catalog_coupon.title, coupon_title)

        course_catalog_vouchers = course_catalog_coupon.attr.coupon_vouchers.vouchers.all()
        self.assertEqual(course_catalog_vouchers.count(), quantity)

        course_catalog_voucher_range = course_catalog_vouchers.first().offers.first().benefit.range
        self.assertEqual(course_catalog_voucher_range.course_catalog, course_catalog)

    def test_create_program_coupon(self):
        """
        Test program coupon voucher creation with specified program uuid.
        """
        coupon_title = 'Program coupon'
        quantity = 1
        program_uuid = uuid.uuid4()

        program_coupon = self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            program_uuid=program_uuid,
            course_seat_types='verified',
        )
        self.assertEqual(program_coupon.title, coupon_title)

        program_vouchers = program_coupon.attr.coupon_vouchers.vouchers.all()
        program_voucher_offer = program_vouchers.first().offers.first()
        self.assertEqual(program_vouchers.count(), quantity)
        self.assertEqual(program_voucher_offer.condition.program_uuid, program_uuid)

    def assert_report_first_row(self, row, coupon, voucher):
        """
        Verify that the first row fields contain the right data.
        Args:
            row (list): First row in report
            coupon (Product): Coupon for which the report is generated
            voucher (Voucher): Voucher associated with the Coupon
        """
        offer = voucher.offers.first()
        if offer.condition.range.catalog:
            discount_data = get_voucher_discount_info(
                offer.benefit,
                offer.condition.range.catalog.stock_records.first().price_excl_tax
            )
            coupon_type = _('Discount') if discount_data['is_discounted'] else _('Enrollment')
            discount_percentage = _('{percentage} %').format(percentage=discount_data['discount_percentage'])
            discount_amount = currency(discount_data['discount_value'])
        else:
            if offer.benefit.type == Benefit.PERCENTAGE:
                coupon_type = _('Discount') if offer.benefit.value < 100 else _('Enrollment')
            else:
                coupon_type = None
            discount_amount = None
            discount_percentage = _('{percentage} %').format(
                percentage=offer.benefit.value) if offer.benefit.type == Benefit.PERCENTAGE else None

        self.assertEqual(row['Coupon Type'], coupon_type)
        self.assertEqual(row['Category'], ProductCategory.objects.get(product=coupon).category.name)
        self.assertEqual(row['Discount Percentage'], discount_percentage)
        self.assertEqual(row['Discount Amount'], discount_amount)
        self.assertEqual(row['Client'], coupon.client.name)
        self.assertEqual(row['Note'], coupon.attr.note)
        self.assertEqual(row['Create Date'], coupon.date_updated.strftime("%b %d, %y"))
        self.assertEqual(row['Coupon Start Date'], voucher.start_datetime.strftime("%b %d, %y"))
        self.assertEqual(row['Coupon Expiry Date'], voucher.end_datetime.strftime("%b %d, %y"))

    def assert_report_row(self, row, voucher):
        """
        Verify that the row fields contain the right data.
        Args:
            row (list): Non first row in report
            coupon (Product): Coupon for which the report is generated
            voucher (Voucher): Voucher associated with the Coupon
        """
        offer = voucher.offers.first()
        if voucher.usage == Voucher.SINGLE_USE:
            max_uses_count = 1
        elif voucher.usage != Voucher.SINGLE_USE and offer.max_global_applications is None:
            max_uses_count = 10000
        else:
            max_uses_count = offer.max_global_applications

        self.assertEqual(row['Maximum Coupon Usage'], max_uses_count)
        self.assertEqual(row['Code'], voucher.code)
        self.assertEqual(
            row['URL'],
            get_ecommerce_url() + self.REDEMPTION_URL.format(voucher.code)
        )

    def test_generate_coupon_report_for_entitlement(self):
        """ Verify the coupon report is generated properly in case of entitlements. """
        self.data['coupon'] = self.entitlement_coupon
        self.data['catalog'] = self.entitlement_catalog
        self.coupon_vouchers = self.entitlement_coupon_vouchers
        self.setup_coupons_for_report()
        client = UserFactory()
        basket = Basket.get_basket(client, self.site)
        basket.add_product(self.entitlement_coupon)

        vouchers = self.coupon_vouchers.first().vouchers.all()
        self.use_voucher('TESTORDER1', vouchers[1], self.user, add_entitlement=True)
        self.mock_course_api_response(course=self.course)
        try:
            generate_coupon_report(self.coupon_vouchers)
        except TypeError:
            self.fail("Exception:ErrorType raised unexpectedly!")

    def test_generate_coupon_report(self):
        """ Verify the coupon report is generated properly. """
        self.setup_coupons_for_report()
        client = UserFactory()
        basket = Basket.get_basket(client, self.site)
        basket.add_product(self.coupon)

        vouchers = self.coupon_vouchers.first().vouchers.all()
        self.use_voucher('TESTORDER1', vouchers[1], self.user)

        user2 = UserFactory()
        self.use_voucher('TESTORDER2', vouchers[2], self.user)
        self.use_voucher('TESTORDER3', vouchers[2], user2)

        self.mock_course_api_response(course=self.course)
        field_names, rows = generate_coupon_report(self.coupon_vouchers)

        self.assertEqual(field_names, [
            'Code',
            'Coupon Name',
            'Maximum Coupon Usage',
            'Redemption Count',
            'Coupon Type',
            'URL',
            'Course ID',
            'Organization',
            'Client',
            'Category',
            'Note',
            'Price',
            'Invoiced Amount',
            'Discount Percentage',
            'Discount Amount',
            'Status',
            'Order Number',
            'Redeemed By Username',
            'Create Date',
            'Coupon Start Date',
            'Coupon Expiry Date',
            'Email Domains',
        ])

        voucher = Voucher.objects.get(name=rows[0]['Coupon Name'])
        self.assert_report_first_row(rows.pop(0), self.coupon, voucher)

        for row in rows:
            voucher = Voucher.objects.get(code=row['Code'])
            self.assert_report_row(row, voucher)

        self.assertNotIn('Catalog Query', field_names)
        self.assertNotIn('Course Seat Types', field_names)
        self.assertNotIn('Redeemed For Course ID', field_names)

    def test_report_for_dynamic_coupon_with_fixed_benefit_type(self):
        """ Verify the coupon report contains correct data for coupon with fixed benefit type. """
        dynamic_coupon = self.create_coupon(
            benefit_type=Benefit.FIXED,
            benefit_value=50,
            catalog_query='*:*',
            course_seat_types='verified',
            max_uses=1,
            note='Tešt note',
            quantity=1,
            title='Tešt product',
            voucher_type=Voucher.MULTI_USE
        )
        coupon_voucher = CouponVouchers.objects.get(coupon=dynamic_coupon)
        __, rows = generate_coupon_report([coupon_voucher])
        voucher = coupon_voucher.vouchers.first()
        self.assert_report_first_row(rows[0], dynamic_coupon, voucher)

    def test_generate_coupon_report_with_deleted_product(self):
        """ Verify the coupon report contains correct data for coupon with fixed benefit type. """
        course = CourseFactory(id='course-v1:del-org+course+run', partner=self.partner)
        professional_seat = course.create_or_update_seat('professional', False, 100)
        query_coupon = self.create_catalog_coupon(catalog_query='course:*')

        vouchers = query_coupon.attr.coupon_vouchers.vouchers.all()
        first_voucher = vouchers.first()
        self.use_voucher('TESTORDER1', first_voucher, self.user, product=professional_seat)
        professional_seat.delete()

        __, rows = generate_coupon_report([query_coupon.attr.coupon_vouchers])
        self.assert_report_first_row(rows[0], query_coupon, first_voucher)
        self.assertDictContainsSubset({'Redeemed For Course ID': 'Unknown'}, rows[2])

    def test_report_for_inactive_coupons(self):
        """ Verify the coupon report show correct status for inactive coupons. """
        self.data.update({
            'name': self.coupon.title,
            'end_datetime': datetime.datetime.now() - datetime.timedelta(days=1)
        })
        vouchers = create_vouchers(**self.data)
        self.coupon_vouchers.first().vouchers.add(*vouchers)

        __, rows = generate_coupon_report(self.coupon_vouchers)

        # The data that is the same for all vouchers like Coupon Name, Coupon Type, etc.
        # are only shown in row[0]
        # The data that is unique among vouchers like Code, Url, Status, etc.
        # starts from row[1]
        self.assertEqual(rows[0]['Coupon Name'], self.coupon.title)
        self.assertEqual(rows[2]['Status'], _('Inactive'))

    def test_generate_coupon_report_for_query_coupons(self):
        """ Verify empty report fields for query coupons. """
        catalog_query = 'course:*'
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url)
        query_coupon = self.create_catalog_coupon(catalog_query=catalog_query)
        field_names, rows = generate_coupon_report([query_coupon.attr.coupon_vouchers])

        empty_fields = (
            'Discount Amount',
            'Price',
        )
        for field in empty_fields:
            self.assertIsNone(rows[0][field])

        self.assertNotIn('Course ID', field_names)
        self.assertNotIn('Organization', field_names)
        self.assertNotIn('Program UUID', field_names)

        self.assertIn('Catalog Query', field_names)
        self.assertEqual(rows[0]['Catalog Query'], catalog_query)

        self.assertIn('Course Seat Types', field_names)
        self.assertEqual(rows[0]['Course Seat Types'], 'verified')

        self.assertIn('Redeemed For Course ID', field_names)
        self.assertNotIn('Redeemed For Course ID', rows[0])

        self.assertIn('Redeemed For Course IDs', field_names)
        self.assertNotIn('Redeemed For Course IDs', rows[0])

    def test_get_voucher_discount_info(self):
        """ Verify that get_voucher_discount_info() returns correct info. """
        benefits = self.create_benefits()

        for benefit in benefits:
            discount_info = get_voucher_discount_info(benefit, self.seat_price)
            if (benefit.type == "Percentage" and benefit.value == 100.00) or \
               (benefit.type == "Absolute" and benefit.value == self.seat_price):
                self.assertEqual(discount_info['discount_percentage'], 100.00)
                self.assertEqual(discount_info['discount_value'], 100.00)
                self.assertFalse(discount_info['is_discounted'])
            else:
                self.assertEqual(discount_info['discount_percentage'], 50.00)
                self.assertEqual(discount_info['discount_value'], 50.00)
                self.assertTrue(discount_info['is_discounted'])

            discount_info = get_voucher_discount_info(benefit, 0.0)
            self.assertEqual(discount_info['discount_percentage'], 0.00)
            self.assertEqual(discount_info['discount_value'], 0.00)
            self.assertFalse(discount_info['is_discounted'])

            discount_info = get_voucher_discount_info(None, 0.0)
            self.assertEqual(discount_info['discount_percentage'], 0.00)
            self.assertEqual(discount_info['discount_value'], 0.00)
            self.assertFalse(discount_info['is_discounted'])

            discount_info = get_voucher_discount_info(None, self.seat_price)
            self.assertEqual(discount_info['discount_percentage'], 0.00)
            self.assertEqual(discount_info['discount_value'], 0.00)
            self.assertFalse(discount_info['is_discounted'])

        discount_info = get_voucher_discount_info(benefits[-1], 20.00)
        self.assertEqual(discount_info['discount_percentage'], 100.00)
        self.assertEqual(discount_info['discount_value'], 20.00)
        self.assertFalse(discount_info['is_discounted'])

    def test_multiple_usage_coupon(self):
        """Test that multiple-usage coupon is created and the usage number decreased on usage."""
        # Verify that the created voucher has two possible applications.
        voucher = self.coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEqual(voucher.offers.first().get_max_applications(), 1)

        # Verify that the voucher now has been applied and usage number decreased.
        basket = self.apply_voucher(self.user, self.site, voucher)
        order = create_order(basket=basket, user=self.user)
        lines = order.lines.all()
        order, completed_lines = CouponFulfillmentModule().fulfill_product(order, lines)
        self.assertEqual(completed_lines[0].status, LINE.COMPLETE)
        self.assertEqual(len(basket.applied_offers()), 1)
        self.assertEqual(voucher.offers.first().get_max_applications(), 0)

        # Verify that the voucher with now 0 usage number wasn't applied to the basket.
        new_basket = self.apply_voucher(self.user, self.site, voucher)
        self.assertEqual(len(new_basket.applied_offers()), 0)

    def test_single_use_redemption_count(self):
        """Verify redemption count does not increment for other, unused, single-use vouchers."""
        coupon = self.create_coupon(
            title='Test single use',
            catalog=self.catalog,
            quantity=2
        )
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        self.use_voucher('TEST', vouchers[0], self.user)
        __, rows = generate_coupon_report([coupon.attr.coupon_vouchers])

        # rows[0] - This row is different from other rows
        # rows[1] - first voucher header row
        # rows[2] - first voucher row with usage information
        # rows[3] - second voucher header row
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1]['Redemption Count'], 1)
        self.assertEqual(rows[2]['Redeemed By Username'], self.user.username)
        self.assertEqual(rows[3]['Redemption Count'], 0)

    def test_generate_coupon_report_for_used_query_coupon(self):
        """Test that used query coupon voucher reports which course was it used for."""
        catalog_query = '*:*'
        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query=catalog_query, course_run=self.course
        )
        self.mock_course_runs_contains_endpoint(
            course_run_ids=[self.verified_seat.course_id], query=catalog_query,
            discovery_api_url=self.site_configuration.discovery_api_url
        )
        query_coupon = self.create_catalog_coupon(catalog_query=catalog_query)
        voucher = query_coupon.attr.coupon_vouchers.vouchers.first()
        voucher.offers.first().condition.range.add_product(self.verified_seat)
        self.use_voucher('TESTORDER4', voucher, self.user)
        field_names, rows = generate_coupon_report([query_coupon.attr.coupon_vouchers])

        self.assertIn('Redeemed For Course ID', field_names)
        self.assertIn('Redeemed By Username', field_names)
        self.assertEqual(rows[-1]['Redeemed By Username'], self.user.username)
        self.assertEqual(rows[-1]['Redeemed For Course ID'], self.course.id)

    def test_generate_coupon_report_for_query_coupon_with_multi_line_order(self):
        """
        Test that coupon report for a query coupon that was used on multi-line order
        contains ids from all courses in that order.
        """
        course1 = CourseFactory()
        course2 = CourseFactory()
        order = OrderFactory(number='TESTORDER')
        order.lines.add(
            OrderLineFactory(
                product=course1.create_or_update_seat('verified', False, 101),
                partner_sku=self.partner_sku
            )
        )
        order.lines.add(
            OrderLineFactory(
                product=course2.create_or_update_seat('verified', False, 110),
                partner_sku=self.partner_sku
            )
        )
        query_coupon = self.create_catalog_coupon(catalog_query='*:*')
        voucher = query_coupon.attr.coupon_vouchers.vouchers.first()
        voucher.record_usage(order, self.user)
        field_names, rows = generate_coupon_report([query_coupon.attr.coupon_vouchers])

        expected_redemed_course_ids = '{}, {}'.format(course1.id, course2.id)
        self.assertEqual(rows[-1]['Redeemed For Course IDs'], expected_redemed_course_ids)
        self.assertEqual(rows[-1].get('Redeemed For Course ID'), None)
        self.assertIn('Redeemed For Course ID', field_names)
        self.assertIn('Redeemed For Course IDs', field_names)

    def test_update_voucher_offer(self):
        """Test updating a voucher."""
        self.data['email_domains'] = 'example.com'
        vouchers = create_vouchers(**self.data)

        voucher = vouchers[0]
        voucher_offer = voucher.offers.first()
        self.assertEqual(voucher_offer.benefit.type, Benefit.PERCENTAGE)
        self.assertEqual(voucher_offer.benefit.value, 100.00)
        self.assertEqual(voucher_offer.benefit.range.catalog, self.catalog)

        new_email_domains = 'example.org'
        new_offer = update_voucher_offer(
            voucher_offer, 50.00, Benefit.PERCENTAGE,
            email_domains=new_email_domains
        )
        self.assertEqual(new_offer.benefit.type, Benefit.PERCENTAGE)
        self.assertEqual(new_offer.benefit.value, 50.00)
        self.assertEqual(new_offer.benefit.range.catalog, self.catalog)
        self.assertEqual(new_offer.email_domains, new_email_domains)

    def test_get_voucher_and_products_from_code(self):
        """ Verify that get_voucher_and_products_from_code() returns products and voucher. """
        original_voucher, original_product = prepare_voucher(code=VOUCHER_CODE)
        voucher, products = get_voucher_and_products_from_code(code=VOUCHER_CODE)

        self.assertIsNotNone(voucher)
        self.assertEqual(voucher, original_voucher)
        self.assertEqual(voucher.code, VOUCHER_CODE)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0], original_product)

    def test_no_product(self):
        """ Verify that an exception is raised if there is no product. """
        voucher = VoucherFactory()
        offer = ConditionalOfferFactory()
        voucher.offers.add(offer)

        with self.assertRaises(exceptions.ProductNotFoundError):
            get_voucher_and_products_from_code(code=voucher.code)

    def test_get_non_existing_voucher(self):
        """ Verify that get_voucher_and_products_from_code() raises exception for a non-existing voucher. """
        with self.assertRaises(Voucher.DoesNotExist):
            get_voucher_and_products_from_code(code=FuzzyText().fuzz())

    def test_generate_coupon_report_for_program_coupon(self):
        """ Only program coupon applicable fields should be shown. """
        program_uuid = uuid.uuid4()
        program_coupon = self.create_coupon(
            title='Program Coupon Report',
            program_uuid=program_uuid,
        )
        field_names, rows = generate_coupon_report([program_coupon.attr.coupon_vouchers])

        for field in ('Discount Amount', 'Price'):
            self.assertIsNone(rows[0][field])

        removed_fields = ('Catalog Query', 'Course ID', 'Course Seat Types', 'Organization', 'Redeemed For Course ID',)
        for field_name in removed_fields:
            self.assertNotIn(field_name, field_names)

        self.assertIn('Program UUID', field_names)
        self.assertEqual(rows[0]['Program UUID'], program_uuid)
