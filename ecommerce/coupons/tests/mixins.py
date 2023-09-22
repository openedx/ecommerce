

import datetime

import mock
import responses
from django.test import RequestFactory
from edx_django_utils.cache import TieredCache
from oscar.core.utils import slugify
from oscar.test import factories

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.core.models import BusinessClient
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.catalogue.utils import create_coupon_product
from ecommerce.tests.factories import PartnerFactory, UserFactory
from ecommerce.tests.mixins import Applicator, Benefit, Catalog, ProductClass, SiteMixin, Voucher


class DiscoveryMockMixin:
    """ Mocks for the Discovery service response. """
    def setUp(self):
        super(DiscoveryMockMixin, self).setUp()
        TieredCache.dangerous_clear_all_tiers()

    @staticmethod
    def build_discovery_catalogs_url(discovery_api_url, catalog_id=''):
        suffix = '{}/'.format(catalog_id) if catalog_id else ''
        return '{discovery_api_url}catalogs/{suffix}'.format(discovery_api_url=discovery_api_url, suffix=suffix)

    def mock_course_run_detail_endpoint(self, course_run, discovery_api_url, course_run_info=None):
        """
        Mocks the course run detail endpoint on the Discovery API.
        """
        if not course_run_info:
            course_run_info = {
                "course": "edX+DemoX",
                "key": course_run.id,
                "title": course_run.name,
                "short_description": 'Foo',
                "start": "2013-02-05T05:00:00Z",
                "image": {
                    "src": "/path/to/image.jpg",
                },
                'enrollment_end': None
            }

        course_run_url = '{}course_runs/{}/?partner={}'.format(
            discovery_api_url,
            course_run.id,
            self.partner.short_code
        )

        responses.add(
            responses.GET, course_run_url,
            json=course_run_info,
            content_type='application/json'
        )

    def mock_course_detail_endpoint(self, discovery_api_url, course=None, course_info=None, course_key=None):
        """
        Mocks the course detail endpoint on the Discovery API.

        Either it will look up by course.attr.UUID or course_key.
        """
        if not course_info:
            course_info = {
                "course": "edX+DemoX",
                "key": "edX+DemoX",
                "title": "edX Demo Course",
                "short_description": 'Foo',
                "image": {
                    "src": "/path/to/image.jpg",
                },
            }

            if course:
                course_info.update({
                    "uuid": course.attr.UUID,
                    "title": course.title
                })

            if course_key:
                course_info.update({
                    "key": course_key
                })

        course_url = '{}courses/{}/'.format(
            discovery_api_url,
            course_key if course_key else course.attr.UUID,
        )

        responses.add(
            responses.GET, course_url,
            json=course_info,
            content_type='application/json'
        )

    def mock_course_detail_endpoint_error(self, course_identifier, discovery_api_url, error):
        """
        Mocks the course detail endpoint on the Discovery API to fake a request error.

        course_identifier can be course UUID or key.
        """

        course_url = '{}courses/{}/'.format(
            discovery_api_url,
            course_identifier,
        )

        responses.add(
            responses.GET, course_url,
            body=error(),
            content_type='application/json'
        )

    def mock_catalog_detail_endpoint(
            self, discovery_api_url, catalog_id=1, expected_query="*:*", expected_status=200
    ):
        """
        Helper function to register a discovery API endpoint for fetching catalog by catalog id.
        """
        course_catalog = {
            "id": catalog_id,
            "name": "All Courses",
            "query": expected_query,
            "courses_count": 1,
            "viewers": []
        }

        responses.add(
            responses.GET,
            self.build_discovery_catalogs_url(discovery_api_url, catalog_id),
            json=course_catalog,
            content_type='application/json',
            status=expected_status,
        )

    def mock_course_runs_endpoint(
            self, discovery_api_url, course_run=None, partner_code=None, query=None, course_run_info=None
    ):
        """
        Helper function to register a discovery API endpoint for getting
        course runs information.
        """
        if not course_run_info:
            course_run_info = {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'key': course_run.id,
                    'title': course_run.name,
                    'start': '2016-05-01T00:00:00Z',
                    'image': {
                        'src': 'path/to/the/course/image'
                    },
                    'enrollment_start': '2016-05-01T00:00:00Z',
                    'enrollment_end': None
                }] if course_run else [{
                    'key': 'test',
                    'title': 'Test course',
                    'enrollment_start': '2016-05-01T00:00:00Z',
                    'enrollment_end': None
                }],
            }
        course_run_url_with_query = '{}course_runs/?q={}'.format(
            discovery_api_url,
            query if query else 'id:course*'
        )
        responses.add(
            responses.GET,
            course_run_url_with_query,
            json=course_run_info,
            content_type='application/json'
        )

        course_run_url_with_query_and_partner_code = '{}course_runs/?q={}&partner={}&limit=100'.format(
            discovery_api_url,
            query if query else 'id:course*',
            partner_code if partner_code else 'edx'
        )
        responses.add(
            responses.GET,
            course_run_url_with_query_and_partner_code,
            json=course_run_info,
            content_type='application/json'
        )

        course_run_url_with_key = '{}course_runs/{}/'.format(
            discovery_api_url,
            course_run.id if course_run else 'course-v1:test+test+test'
        )
        responses.add(
            responses.GET, course_run_url_with_key,
            json=course_run_info['results'][0],
            content_type='application/json'
        )

        course_run_url_with_key_and_partner = '{}course_runs/{}/?partner={}'.format(
            discovery_api_url,
            course_run.id if course_run else 'course-v1:test+test+test',
            partner_code if partner_code else 'edx'
        )
        responses.add(
            responses.GET, course_run_url_with_key_and_partner,
            json=course_run_info['results'][0],
            content_type='application/json'
        )

    def mock_enterprise_catalog_course_endpoint(
            self, enterprise_api_url, enterprise_catalog_id, course_run=None, course_info=None
    ):
        """
        Helper function to register a enterprise API endpoint for getting course information.
        """
        if not course_info:
            course_info = {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'key': course_run.id,
                    'title': course_run.name,
                    'card_image_url': 'path/to/the/course/image',
                    'content_type': 'course',
                    'course_runs': [{
                        'key': course_run.id,
                        'start': '2016-05-01T00:00:00Z',
                        'enrollment_start': '2016-05-01T00:00:00Z',
                        'enrollment_end': None,
                    }, {
                        'key': 'test',
                        'title': 'Test course',
                    }],
                }] if course_run else [{
                    'key': 'test',
                    'title': 'Test course',
                    'course_runs': [],
                }],
            }
        enterprise_catalog_url = '{}enterprise_catalogs/{}/'.format(
            enterprise_api_url,
            enterprise_catalog_id
        )
        responses.add(
            responses.GET,
            enterprise_catalog_url,
            json=course_info,
            content_type='application/json'
        )

    def mock_course_runs_contains_endpoint(self, course_run_ids, query, discovery_api_url):
        """
        Helper function to register a dynamic discovery API endpoint for the contains information.
        """
        course_contains_info = {
            'course_runs': {}
        }
        for course_run_id in course_run_ids:
            course_contains_info['course_runs'][course_run_id] = True

        course_run_url = '{}course_runs/contains/?course_run_ids={}&query={}'.format(
            discovery_api_url,
            ",".join(course_run_id for course_run_id in course_run_ids),
            query if query else 'id:course*'
        )
        responses.add(
            responses.GET, course_run_url,
            json=course_contains_info,
            content_type='application/json'
        )

    def mock_course_runs_contains_endpoint_failure(self, course_run_ids, catalog_id, error, discovery_api_url):
        """
        Helper function to register a discovery API endpoint with failure
        for getting course runs information.
        """
        catalog_contains_course_run_url = '{}catalogs/{}/contains/?course_run_id={}'.format(
            discovery_api_url,
            catalog_id,
            ','.join(course_run_id for course_run_id in course_run_ids),
        )
        responses.add(
            method=responses.GET,
            url=catalog_contains_course_run_url,
            body=error(),
            content_type='application/json',
            status=500
        )

    def mock_catalog_query_contains_endpoint(
        self, course_run_ids, course_uuids, absent_ids, query, discovery_api_url, partner='edx'
    ):
        query_contains_info = {str(identifier): True for identifier in course_run_ids + course_uuids}
        for identifier in absent_ids:
            query_contains_info[str(identifier)] = False
        url = (
            '{}catalog/query_contains/?course_run_ids={}&course_uuids={}&query={}&partner={}'
        ).format(
            discovery_api_url,
            ",".join(course_run_id for course_run_id in course_run_ids),
            ",".join(str(course_uuid) for course_uuid in course_uuids),
            query,
            partner
        ).replace("+", "%2B")
        responses.add(
            responses.GET, url,
            json=query_contains_info,
            content_type='application/json'
        )
        return url

    def mock_catalog_contains_endpoint(
            self, discovery_api_url, catalog_id=1, course_run_ids=None
    ):
        """
        Helper function to register discovery contains API endpoint.
        """
        course_run_ids = course_run_ids or []
        courses = {course_run_id: True for course_run_id in course_run_ids}

        course_discovery_api_response = {
            'courses': courses
        }
        catalog_contains_uri = '{}contains/?course_run_id={}'.format(
            self.build_discovery_catalogs_url(discovery_api_url, catalog_id), ','.join(course_run_ids)
        ).replace("+", "%2B")
        responses.add(
            method=responses.GET,
            url=catalog_contains_uri,
            json=course_discovery_api_response,
            content_type='application/json'
        )

    def mock_discovery_api(self, catalog_name_list, discovery_api_url):
        """
        Helper function to register discovery API endpoint for a
        single catalog or multiple catalogs response.
        """
        mocked_results = []
        for catalog_index, catalog_name in enumerate(catalog_name_list):
            mocked_results.append(
                {
                    'id': catalog_index + 1,
                    'name': catalog_name,
                    'query': 'title: *',
                    'courses_count': 0,
                    'viewers': []
                }
            )

        course_discovery_api_response = {
            'count': len(catalog_name_list),
            'next': None,
            'previous': None,
            'results': mocked_results
        }

        responses.add(
            method=responses.GET,
            url=self.build_discovery_catalogs_url(discovery_api_url),
            json=course_discovery_api_response,
            content_type='application/json'
        )

    def mock_discovery_api_for_paginated_catalogs(self, catalog_name_list, discovery_api_url):
        """
        Helper function to register discovery API endpoint for multiple
        catalogs with paginated response.
        """
        discovery_catalogs_url = self.build_discovery_catalogs_url(discovery_api_url)

        for catalog_index, catalog_name in enumerate(catalog_name_list):
            catalog_id = catalog_index + 1
            mocked_result = {
                'id': catalog_id,
                'name': catalog_name,
                'query': 'title: *',
                'courses_count': 0,
                'viewers': []
            }

            next_page_url = None
            if catalog_id < len(catalog_name_list):
                # Not a last page so there will be more catalogs for another page
                next_page_url = '{}?limit=1&offset={}'.format(
                    discovery_catalogs_url,
                    catalog_id
                )

            previous_page_url = None
            if catalog_index != 0:
                # Not a first page so there will always be catalogs on previous page
                previous_page_url = '{}?limit=1&offset={}'.format(
                    discovery_catalogs_url,
                    catalog_index
                )

            course_discovery_api_paginated_response = {
                'count': len(catalog_name_list),
                'next': next_page_url,
                'previous': previous_page_url,
                'results': [mocked_result]
            }

            responses.add(
                method=responses.GET,
                url=discovery_catalogs_url,
                json=course_discovery_api_paginated_response,
                content_type='application/json'
            )

    def mock_discovery_api_failure(self, error, discovery_api_url, catalog_id=None):
        """
        Helper function to register discovery API endpoint for catalogs
        with failure.
        """
        responses.add(
            method=responses.GET,
            url=self.build_discovery_catalogs_url(discovery_api_url, catalog_id),
            body=error(),
            content_type='application/json',
            status=500
        )


class CouponMixin(SiteMixin):
    """ Mixin for preparing data for coupons and creating coupons. """

    REDEMPTION_URL = "/coupons/offer/?code={}"

    def setUp(self):
        super(CouponMixin, self).setUp()
        self.category = factories.CategoryFactory()

        # Force the creation of a coupon ProductClass
        self.coupon_product_class  # pylint: disable=pointless-statement

    @property
    def coupon_product_class(self):
        defaults = {'requires_shipping': False, 'track_stock': False, 'name': COUPON_PRODUCT_CLASS_NAME}
        pc, created = ProductClass.objects.get_or_create(
            name=COUPON_PRODUCT_CLASS_NAME, slug=slugify(COUPON_PRODUCT_CLASS_NAME), defaults=defaults
        )

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
            factories.ProductAttributeFactory(
                product_class=pc,
                name='Notification Email',
                code='notify_email',
                type='text'
            )

            factories.ProductAttributeFactory(
                product_class=pc,
                name='Sales Force ID',
                code='sales_force_id',
                type='text'
            )

            factories.ProductAttributeFactory(
                product_class=pc,
                name='Salesforce Opportunity Line Item',
                code='salesforce_opportunity_line_item',
                type='text'
            )

        return pc

    def create_coupon(self, benefit_type=Benefit.PERCENTAGE, benefit_value=100, catalog=None, catalog_query=None,
                      client=None, code='', course_seat_types=None, email_domains=None, enterprise_customer=None,
                      enterprise_customer_catalog=None, max_uses=None, note=None, partner=None, price=100, quantity=5,
                      title='Test coupon', voucher_type=Voucher.SINGLE_USE, course_catalog=None, program_uuid=None,
                      start_datetime=None, end_datetime=None, sales_force_id=None,
                      salesforce_opportunity_line_item=None):
        """Helper method for creating a coupon.

        Arguments:
            benefit_type(str): The voucher benefit type
            benefit_value(int): The voucher benefit value
            catalog(Catalog): Catalog of courses for which the coupon applies
            catalog_query(str): Course query string
            client (BusinessClient):  Optional business client object
            code(str): Custom coupon code
            course_catalog (int): Course catalog id from Discovery Service
            course_seat_types(str): A string of comma-separated list of seat types
            enterprise_customer (str): Hex-encoded UUID for an Enterprise Customer object from the Enterprise app.
            enterprise_customer_catalog (str): UUID for an Enterprise Customer Catalog from the Enterprise app.
            email_domains(str): A comma seperated list of email domains
            max_uses (int): Number of Voucher max uses
            note (str): Coupon note.
            partner(Partner): Partner used for creating a catalog
            price(int): Price of the coupon
            quantity (int): Number of vouchers to be created and associated with the coupon
            title(str): Title of the coupon
            voucher_type (str): Voucher type
            program_uuid (str): Program UUID
            sales_force_id (str): Sales Force Opprtunity ID
            salesforce_opportunity_line_item (str): Sales Force Opportunity Line Item ID

        Returns:
            coupon (Coupon)

        """
        if partner is None:
            partner = PartnerFactory(name='Tester')
        if client is None:
            client, __ = BusinessClient.objects.get_or_create(name='Test Client')
        if (catalog is None and not enterprise_customer_catalog and not
                ((catalog_query or course_catalog or program_uuid) and course_seat_types)):
            catalog = Catalog.objects.create(partner=partner)
        if code != '':
            quantity = 1

        with mock.patch(
                "ecommerce.extensions.voucher.utils.get_enterprise_customer",
                mock.Mock(return_value={'name': 'Fake enterprise'})):
            coupon = create_coupon_product(
                benefit_type=benefit_type,
                benefit_value=benefit_value,
                catalog=catalog,
                catalog_query=catalog_query,
                category=self.category,
                code=code,
                course_catalog=course_catalog,
                course_seat_types=course_seat_types,
                email_domains=email_domains,
                end_datetime=end_datetime or (datetime.datetime.now() + datetime.timedelta(days=500)),
                enterprise_customer=enterprise_customer,
                enterprise_customer_catalog=enterprise_customer_catalog,
                max_uses=max_uses,
                note=note,
                partner=partner,
                price=price,
                quantity=quantity,
                start_datetime=start_datetime or datetime.datetime(2015, 1, 1),
                title=title,
                voucher_type=voucher_type,
                program_uuid=program_uuid,
                site=self.site,
                sales_force_id=sales_force_id,
                salesforce_opportunity_line_item=salesforce_opportunity_line_item,
            )

        request = RequestFactory()
        request.site = self.site
        request.user = UserFactory()
        request.COOKIES = {}
        request.GET = {}

        self.basket = prepare_basket(request, [coupon])

        view = CouponViewSet()
        view.request = request

        self.response_data = view.create_order_for_invoice(self.basket, coupon_id=coupon.id, client=client)
        coupon.client = client

        return coupon

    def apply_voucher(self, user, site, voucher):
        """ Apply the voucher to a basket. """
        basket = factories.BasketFactory(owner=user, site=site)
        product = voucher.offers.first().benefit.range.all_products()[0]
        basket.add_product(product)
        basket.vouchers.add(voucher)
        Applicator().apply(basket, self.user)
        return basket
