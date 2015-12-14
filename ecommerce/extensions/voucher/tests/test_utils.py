import datetime

from django.conf import settings
from django.db import IntegrityError
from django.test import override_settings
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.voucher.utils import create_vouchers, generate_voucher_report
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
CouponVouchers = get_model('voucher', 'CouponVouchers')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

VOUCHER_CODE_LENGTH = 1


class UtilTests(TestCase):

    course_id = 'edX/DemoX/Demo_Course'
    certificate_type = 'test-certificate-type'
    provider = None

    def setUp(self):
        super(UtilTests, self).setUp()

        self.catalog = Catalog.objects.create(partner=self.partner)

        self.coupon_product_class, _ = ProductClass.objects.get_or_create(name='coupon')
        self.coupon = factories.create_product(
            product_class=self.coupon_product_class,
            title='Test product'
        )

        self.stock_record = factories.create_stockrecord(self.coupon, num_in_stock=2)
        self.catalog.stock_records.add(self.stock_record)

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
        self.assertEqual(len(coupon_voucher.vouchers.all()), 10)
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
            code="XMASC0DE"
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
                code="XMASC0DE"
            )

    def test_generate_voucher_report(self):
        """
        Test generate voucher report
        """
        vouchers = []

        for i in range(10):
            vouchers.extend(
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
                    code=chr(65+i)*8
                )
            )

        for voucher in vouchers:
            voucher.discount = "100.00 %"
            voucher.url = settings.ECOMMERCE_URL_ROOT + "/coupons/redeem/?code={}".format(voucher.code)

        field_names, rows = generate_voucher_report(vouchers)

        self.assertListEqual(field_names, ['Name', 'Code', 'Discount', 'URL'])

        for i in range(10):
            voucher_code = chr(65+i)*8
            self.assertDictEqual(
                rows[i],
                {
                    'Name': 'Test voucher',
                    'Code': voucher_code,
                    'Discount': '100.00 %',
                    'URL': settings.ECOMMERCE_URL_ROOT + "/coupons/redeem/?code={}".format(voucher_code)
                }
            )
