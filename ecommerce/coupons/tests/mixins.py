# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import json

import httpretty
import pytz
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory
from django.utils.timezone import now
from oscar.test import factories

from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import create_coupon_product
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.invoice.models import Invoice
from ecommerce.tests.factories import BusinessClientFactory, CatalogFactory, PartnerFactory
from ecommerce.tests.mixins import ProductClass, Benefit, Voucher, Applicator


class CourseCatalogMockMixin(object):
    """ Mocks for the Course Catalog responses. """

    def setUp(self):
        super(CourseCatalogMockMixin, self).setUp()
        cache.clear()

    def mock_dynamic_catalog_course_runs_api(self, course_run=None, query=None, course_run_info=None):
        """ Helper function to register a dynamic course catalog API endpoint for the course run information. """
        if not course_run_info:
            course_run_info = {
                'count': 1,
                'next': 'path/to/next/page',
                'results': [{
                    'key': course_run.id,
                    'title': course_run.name,
                    'start': '2016-05-01T00:00:00Z',
                    'image': {
                        'src': 'path/to/the/course/image'
                    }
                }] if course_run else [{
                    'key': 'test',
                    'title': 'Test course',
                }],
            }
        course_run_info_json = json.dumps(course_run_info)
        course_run_url = '{}course_runs/?q={}'.format(
            settings.COURSE_CATALOG_API_URL,
            query if query else 'id:course*'
        )
        httpretty.register_uri(
            httpretty.GET, course_run_url,
            body=course_run_info_json,
            content_type='application/json'
        )

    def mock_dynamic_catalog_contains_api(self, course_run_ids, query):
        """ Helper function to register a dynamic course catalog API endpoint for the contains information. """
        course_contains_info = {
            'course_runs': {}
        }
        for course_run_id in course_run_ids:
            course_contains_info['course_runs'][course_run_id] = True

        course_run_info_json = json.dumps(course_contains_info)
        course_run_url = '{}course_runs/contains/?course_run_ids={}&query={}'.format(
            settings.COURSE_CATALOG_API_URL,
            (course_run_id for course_run_id in course_run_ids),
            query if query else 'id:course*'
        )
        httpretty.register_uri(
            httpretty.GET, course_run_url,
            body=course_run_info_json,
            content_type='application/json'
        )


class CouponMixin(CourseCatalogTestMixin):
    """ Mixin for preparing data for coupons and creating coupons. """

    REDEMPTION_URL = "/coupons/offer/?code={}"

    def setUp(self):
        super(CouponMixin, self).setUp()
        # Force the creation of a coupon ProductClass
        self.coupon_product_class  # pylint: disable=pointless-statement
        self.category = factories.CategoryFactory()

        self.create_and_login_user()
        self.course, self.seat = self.create_course_and_seat(
            id_verification=True,
            partner=self.partner
        )

        self.coupon_data = {
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog_query': None,
            'category': self.category.name,
            'client': 'Člient',
            'code': '',
            'course_seat_types': [],
            'end_datetime': '2020-1-1',
            'max_uses': None,
            'note': None,
            'price': 100,
            'quantity': 2,
            'start_datetime': '2015-1-1',
            'stock_record_ids': [self.seat.stockrecords.first().id],
            'title': 'Tešt Čoupon',
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
        }

        self.invoice_data = {
            'invoice_discount_type': None,
            'invoice_discount_value': 77,
            'invoice_type': Invoice.PREPAID,
            'invoice_number': 'INVOIĆE-00001',
            'invoice_payment_date': datetime.datetime(2015, 1, 1, tzinfo=pytz.UTC).isoformat(),
        }

    @property
    def coupon_product_class(self):
        defaults = {'requires_shipping': False, 'track_stock': False, 'name': 'Coupon'}
        pc, created = ProductClass.objects.get_or_create(name='Coupon', slug='coupon', defaults=defaults)

        if created:
            factories.ProductAttributeFactory(
                code='coupon_vouchers',
                name='Coupon vouchers',
                product_class=pc,
                type='entity'
            )
            factories.ProductAttributeFactory(
                code='note',
                name='Note',
                product_class=pc,
                type='text'
            )

        return pc

    def apply_voucher(self, user, site, voucher):
        """ Apply the voucher to a basket. """
        basket = factories.BasketFactory(owner=user, site=site)
        product = voucher.offers.first().benefit.range.all_products()[0]
        basket.add_product(product)
        basket.vouchers.add(voucher)
        Applicator().apply(basket, self.user)
        return basket

    def assert_invoice_serialized_data(self, coupon_data):
        """ Assert that the coupon details show the invoice data. """
        invoice_details = coupon_data['payment_information']['Invoice']
        self.assertEqual(invoice_details['type'], self.coupon_data['invoice_type'])
        self.assertEqual(invoice_details['number'], self.coupon_data['invoice_number'])
        self.assertEqual(invoice_details['discount_type'], self.coupon_data['invoice_discount_type'])
        self.assertEqual(invoice_details['discount_value'], self.coupon_data['invoice_discount_value'])

    def create_coupon(
            self,
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=100,
            catalog=None,
            catalog_query=None,
            client=None,
            code='',
            course_seat_types=None,
            end_datetime=(now() + datetime.timedelta(days=15)),
            invoice_data=None,
            max_uses=None,
            note=None,
            partner=None,
            price=100,
            quantity=1,
            start_datetime=(now() - datetime.timedelta(days=15)),
            title='Test coupon',
            voucher_type=Voucher.SINGLE_USE
    ):
        """
        Helper method for creating a coupon and associated vouchers.

        Arguments:
            benefit_type(str): Benefit type associated with vouchers.
            benefit_value(int): Benefit value associated with vouchers.
            catalog(Catalog): Catalog of course seats for which vouchers apply.
            catalog_query(str): ElasticSearch query for Dynamic Coupons.
            category(Category): Product Category associated with the coupon.
            client(BusinessClient): Client for the Coupon Order.
            code(str): Custom unique voucher code.
            course_seat_types(str): A comma-separated list of seat types.
            end_datetime(datetime): Voucher expiration datetime.
            invoice_data(dict): Coupon invoice data.
            max_uses(int): Number of Voucher max uses.
            note(str): Coupon description.
            partner(Partner): Partner used to create the Catalog.
            price(int): Course seat price.
            quantity(int): Number of Vouchers associated with the Coupon.
            start_datetime(datetime): Start datetime of Voucher Offer.
            title(str): Title of the Coupon and name of all associated Vouchers.
            voucher_type(str): Voucher type.
        """
        if partner is None:
            partner = PartnerFactory(name='Tester')
        if catalog is None and not (catalog_query and course_seat_types):
            catalog = CatalogFactory(partner=partner)
        if client is None:
            client = BusinessClientFactory()
        if invoice_data is None:
            invoice_data = {
                'invoice_type': Invoice.PREPAID,
                'invoice_number': 'INVOIĆE-00001',
                'invoice_payment_date': now(),
                'invoice_discount_type': None,
                'invoice_discount_value': 77
            }
        self.coupon = create_coupon_product(
            benefit_type=benefit_type,
            benefit_value=benefit_value,
            catalog=catalog,
            catalog_query=catalog_query,
            category=self.category,
            code=code,
            course_seat_types=course_seat_types,
            end_datetime=end_datetime,
            max_uses=max_uses,
            note=note,
            partner=partner,
            price=price,
            quantity=quantity,
            start_datetime=start_datetime,
            title=title,
            voucher_type=voucher_type
        )

        request = RequestFactory()
        request.site = self.site
        request.user = factories.UserFactory()
        request.COOKIES = {}
        self.basket = prepare_basket(request, self.coupon)

        EdxOrderPlacementMixin().create_order_for_invoice(
            basket=self.basket,
            client=client,
            invoice_data=invoice_data
        )
        self.coupon.client = client
        self.coupon.history.all().update(history_user=self.user)

    def update_prepaid_invoice_data(self):
        """ Update the 'data' class variable with invoice information. """
        self.coupon_data.update(self.invoice_data)
