import httpretty
from django.db import IntegrityError
from django.test import override_settings
from oscar.templatetags.currency_filters import currency
from oscar.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.voucher.utils import create_vouchers, generate_coupon_report, get_voucher_discount_info
from ecommerce.tests.mixins import CouponMixin, LmsApiMockMixin
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


class UtilTests(CouponMixin, CourseCatalogTestMixin, LmsApiMockMixin, TestCase):

    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(UtilTests, self).setUp()

        self.user = self.create_user(full_name="Test User", is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory()
        self.verified_seat = self.course.create_or_update_seat('verified', False, 100, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)

        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()
        self.seat_price = self.stock_record.price_excl_tax
        self.catalog.stock_records.add(self.stock_record)

        self.coupon = self.create_coupon(title='Test product', catalog=self.catalog, note='Test note')
        self.coupon.history.all().update(history_user=self.user)
        self.coupon_vouchers = CouponVouchers.objects.filter(coupon=self.coupon)

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
        create_vouchers(
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=50.00,
            catalog=self.catalog,
            coupon=self.coupon,
            end_datetime=datetime.date(2015, 10, 30),
            name="Discount code",
            quantity=1,
            start_datetime=datetime.date(2015, 10, 1),
            voucher_type=Voucher.SINGLE_USE,
            code=VOUCHER_CODE
        )

        create_vouchers(
            benefit_type=Benefit.FIXED,
            benefit_value=100.00,
            catalog=self.catalog,
            coupon=self.coupon,
            end_datetime=datetime.date.today() + datetime.timedelta(10),
            name="Enrollment code",
            quantity=1,
            start_datetime=datetime.date.today() - datetime.timedelta(1),
            voucher_type=Voucher.SINGLE_USE
        )

    def use_voucher(self, voucher, users):
        """
        Mark voucher as used by provided users

        Args:
            voucher (Voucher): voucher to be marked as used
            users (list): list of users
        """
        for user in users:
            voucher.record_usage(OrderFactory(), user)

    def validate_report_of_redeemed_vouchers(self, row, user_ids, usernames):
        self.assertEqual(row['Status'], 'Redeemed')
        self.assertEqual(row['Redeemed By ID'], user_ids)
        self.assertEqual(row['Redeemed By Username'], usernames)

        self.assertEqual(row['Status'], 'Redeemed')
        self.assertEqual(row['Redeemed By ID'], user_ids)
        self.assertEqual(row['Redeemed By Username'], usernames)

    def test_create_vouchers(self):
        """
        Test voucher creation
        """
        vouchers = create_vouchers(
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=100.00,
            catalog=self.catalog,
            coupon=self.coupon,
            end_datetime=datetime.date(2015, 10, 30),
            name="Test voucher",
            quantity=10,
            start_datetime=datetime.date(2015, 10, 1),
            voucher_type=Voucher.SINGLE_USE
        )

        self.assertEqual(len(vouchers), 10)

        voucher = vouchers[0]
        voucher_offer = voucher.offers.first()
        coupon_voucher = CouponVouchers.objects.get(coupon=self.coupon)

        self.assertEqual(voucher_offer.benefit.type, Benefit.PERCENTAGE)
        self.assertEqual(voucher_offer.benefit.value, 100.00)
        self.assertEqual(voucher_offer.benefit.range.catalog, self.catalog)
        self.assertEqual(len(coupon_voucher.vouchers.all()), 15)
        self.assertEqual(voucher.end_datetime, datetime.date(2015, 10, 30))
        self.assertEqual(voucher.start_datetime, datetime.date(2015, 10, 1))
        self.assertEqual(voucher.usage, Voucher.SINGLE_USE)

    @override_settings(VOUCHER_CODE_LENGTH=VOUCHER_CODE_LENGTH)
    def test_regenerate_voucher_code(self):
        """
        Test that voucher code will be regenerated if it already exists
        """
        for code in 'BCDFGHJKL':
            create_vouchers(
                benefit_type=Benefit.PERCENTAGE,
                benefit_value=100.00,
                catalog=self.catalog,
                coupon=self.coupon,
                end_datetime=datetime.date(2015, 10, 30),
                name="Test voucher",
                quantity=1,
                start_datetime=datetime.date(2015, 10, 1),
                voucher_type=Voucher.SINGLE_USE,
                code=code
            )

        for _ in range(20):
            voucher = create_vouchers(
                benefit_type=Benefit.PERCENTAGE,
                benefit_value=100.00,
                catalog=self.catalog,
                coupon=self.coupon,
                end_datetime=datetime.date(2015, 10, 30),
                name="Test voucher",
                quantity=1,
                start_datetime=datetime.date(2015, 10, 1),
                voucher_type=Voucher.SINGLE_USE
            )
            self.assertTrue(Voucher.objects.filter(code__iexact=voucher[0].code).exists())

    @override_settings(VOUCHER_CODE_LENGTH=0)
    def test_nonpositive_voucher_code_length(self):
        """
        Test that setting a voucher code length to a nonpositive integer value
        raises a ValueError
        """
        with self.assertRaises(ValueError):
            create_vouchers(
                benefit_type=Benefit.PERCENTAGE,
                benefit_value=100.00,
                catalog=self.catalog,
                coupon=self.coupon,
                end_datetime=datetime.date(2015, 10, 30),
                name="Test voucher",
                quantity=1,
                start_datetime=datetime.date(2015, 10, 1),
                voucher_type=Voucher.SINGLE_USE
            )

    def test_create_discount_coupon(self):
        """
        Test discount voucher creation with specified code
        """
        discount_vouchers = create_vouchers(
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=25.00,
            catalog=self.catalog,
            coupon=self.coupon,
            end_datetime=datetime.date(2015, 10, 30),
            name="Discount code",
            quantity=1,
            start_datetime=datetime.date(2015, 10, 1),
            voucher_type=Voucher.SINGLE_USE,
            code=VOUCHER_CODE
        )

        self.assertEqual(len(discount_vouchers), 1)
        self.assertEqual(discount_vouchers[0].code, "XMASC0DE")

        with self.assertRaises(IntegrityError):
            create_vouchers(
                benefit_type=Benefit.PERCENTAGE,
                benefit_value=35.00,
                catalog=self.catalog,
                coupon=self.coupon,
                end_datetime=datetime.date(2015, 10, 30),
                name="Discount name",
                quantity=1,
                start_datetime=datetime.date(2015, 10, 1),
                voucher_type=Voucher.SINGLE_USE,
                code=VOUCHER_CODE
            )

    @httpretty.activate
    def test_generate_coupon_report(self):
        self.setup_coupons_for_report()

        client = UserFactory()
        basket = Basket.get_basket(client, self.site)
        basket.add_product(self.coupon)

        vouchers = self.coupon_vouchers.first().vouchers.all()
        self.use_voucher(vouchers.first(), [self.user])

        user2 = UserFactory()
        self.use_voucher(vouchers[1], [self.user, user2])

        category = ProductCategory.objects.get(product=self.coupon).category.name

        self.mock_course_api_response(course=self.course)
        field_names, rows = generate_coupon_report(self.coupon_vouchers)

        self.assertEqual(field_names, [
            'Coupon Name',
            'Code',
            'Coupon Type',
            'URL',
            'CourseID',
            'Partner',
            'Client',
            'Category',
            'Note',
            'Price',
            'Invoiced Amount',
            'Discount Percentage',
            'Discount Amount',
            'Status',
            'Redeemed By ID',
            'Redeemed By Username',
            'Created By',
            'Create Date',
            'Coupon Start Date',
            'Coupon Expiry Date',
        ])

        self.validate_report_of_redeemed_vouchers(rows[0], str(self.user.id), self.user.username)
        self.validate_report_of_redeemed_vouchers(
            rows[1],
            '{}, {}'.format(self.user.id, user2.id),
            '{}, {}'.format(self.user.username, user2.username)
        )

        enrollment_code_row = rows[-2]
        self.assertEqual(enrollment_code_row['Coupon Name'], 'Discount code')
        self.assertEqual(enrollment_code_row['Code'], VOUCHER_CODE)
        self.assertEqual(enrollment_code_row['Coupon Type'], 'Discount')
        self.assertEqual(enrollment_code_row['URL'], get_ecommerce_url() + self.REDEMPTION_URL.format(VOUCHER_CODE))
        self.assertEqual(enrollment_code_row['CourseID'], self.course.id)
        self.assertEqual(enrollment_code_row['Partner'], 'test')
        self.assertEqual(enrollment_code_row['Client'], self.coupon.client.name)
        self.assertEqual(enrollment_code_row['Category'], category)
        self.assertEqual(enrollment_code_row['Note'], self.coupon.attr.note)
        self.assertEqual(enrollment_code_row['Price'], currency(100.00))
        self.assertEqual(enrollment_code_row['Invoiced Amount'], currency(100.00))
        self.assertEqual(enrollment_code_row['Discount Percentage'], '50.0 %')
        self.assertEqual(enrollment_code_row['Discount Amount'], '$50.00')
        self.assertEqual(enrollment_code_row['Status'], 'Inactive')
        self.assertEqual(enrollment_code_row['Redeemed By ID'], '')
        self.assertEqual(enrollment_code_row['Redeemed By Username'], '')
        self.assertEqual(enrollment_code_row['Created By'], self.user.full_name)
        self.assertEqual(
            enrollment_code_row['Create Date'],
            self.coupon.history.latest().history_date.strftime("%b %d,%y")
        )
        self.assertEqual(enrollment_code_row['Coupon Start Date'], 'Oct 01,15')
        self.assertEqual(enrollment_code_row['Coupon Expiry Date'], 'Oct 30,15')

        enrollment_code_row = rows[-1]
        self.assertEqual(enrollment_code_row['Coupon Name'], 'Enrollment code')
        self.assertEqual(len(enrollment_code_row['Code']), settings.VOUCHER_CODE_LENGTH)
        self.assertEqual(enrollment_code_row['Coupon Type'], 'Enrollment')
        self.assertEqual(enrollment_code_row['Category'], category)
        self.assertEqual(enrollment_code_row['Discount Percentage'], '100.0 %')
        self.assertEqual(enrollment_code_row['Discount Amount'], '$100.00')
        self.assertEqual(enrollment_code_row['Redeemed By ID'], '')
        self.assertEqual(enrollment_code_row['Redeemed By Username'], '')
        self.assertEqual(
            enrollment_code_row['URL'],
            get_ecommerce_url() + self.REDEMPTION_URL.format(enrollment_code_row['Code'])
        )

    @httpretty.activate
    def test_generate_coupon_report_for_old_coupons(self):
        self.setup_coupons_for_report()

        Order.objects.get(basket=self.basket).delete()

        self.mock_course_api_response(course=self.course)
        __, rows = generate_coupon_report(self.coupon_vouchers)

        for row in rows:
            self.assertEqual(row['Client'], self.basket.owner.username)

    def test_get_voucher_discount_info(self):
        benefits = self.create_benefits()

        for benefit in benefits:
            discount_info = get_voucher_discount_info(benefit, self.seat_price)
            if (
                    benefit.type == "Percentage" and benefit.value == 100.00 or
                    benefit.type == "Absolute" and benefit.value == self.seat_price
            ):
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
