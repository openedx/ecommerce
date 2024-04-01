import mock
from django.conf import settings

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.iap.api.v1.utils import (
    AppStoreRequestException,
    apply_price_of_inapp_purchase,
    create_inapp_purchase,
    create_ios_product,
    get_auth_headers,
    localize_inapp_purchase,
    products_in_basket_already_purchased,
    set_territories_of_in_app_purchase,
    submit_in_app_purchase_for_review,
    upload_screenshot_of_inapp_purchase
)
from ecommerce.extensions.iap.utils import create_child_products_for_mobile
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.tests.testcases import TestCase


class TestProductsInBasketPurchased(TestCase):
    """ Tests for products_in_basket_already_purchased method. """

    def setUp(self):
        super(TestProductsInBasketPurchased, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.basket = create_basket(
            owner=self.user, site=self.site, price='50.0', product_class=product.product_class
        )
        create_order(site=self.site, user=self.user, basket=self.basket)

    def test_already_purchased(self):
        """
        Test products in basket already purchased by user
        """
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            return_value = products_in_basket_already_purchased(self.user, self.basket, self.site)
            self.assertTrue(return_value)

    def test_not_purchased_yet(self):
        """
        Test products in basket not yet purchased by user
        """
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=False):
            return_value = products_in_basket_already_purchased(self.user, self.basket, self.site)
            self.assertFalse(return_value)


@mock.patch('ecommerce.extensions.iap.api.v1.utils.jwt.encode', return_value='Test token')
class TestCreateIosProducts(TestCase):
    """ Tests for ios product creation on appstore. """

    def setUp(self):
        super(TestCreateIosProducts, self).setUp()
        self.configuration = settings.PAYMENT_PROCESSOR_CONFIG['edx']['ios-iap']
        self.course = CourseFactory(partner=self.partner)
        self.product = self.course.create_or_update_seat('verified', True, 50)
        _, self.ios_seat = create_child_products_for_mobile(self.product.parent)

    @mock.patch('ecommerce.extensions.iap.api.v1.utils.create_inapp_purchase', return_value='12345')
    @mock.patch('ecommerce.extensions.iap.api.v1.utils.localize_inapp_purchase')
    @mock.patch('ecommerce.extensions.iap.api.v1.utils.apply_price_of_inapp_purchase')
    @mock.patch('ecommerce.extensions.iap.api.v1.utils.upload_screenshot_of_inapp_purchase')
    @mock.patch('ecommerce.extensions.iap.api.v1.utils.set_territories_of_in_app_purchase')
    @mock.patch('ecommerce.extensions.iap.api.v1.utils.submit_in_app_purchase_for_review', return_value=None)
    def test_create_ios_product(self, _, __, ___, ____, _____, ______, _______):
        course = {
            'key': 'test',
            'name': 'test',
            'price': '123'
        }
        error_msg = create_ios_product(course, self.ios_seat, self.configuration)
        self.assertEqual(error_msg, None)

    # @mock.patch('ecommerce.extensions.iap.api.v1.utils.create_inapp_purchase')
    def test_create_ios_product_with_failure(self, _):
        course = {
            'key': 'test',
            'name': 'test',
            'price': '123'
        }
        error_msg = create_ios_product(course, self.ios_seat, self.configuration)
        expected_msg = "[Couldn't create inapp purchase id]  for course [{}] with sku [{}]".format(
            course['key'], self.ios_seat.partner_sku)
        self.assertEqual(error_msg, expected_msg)

    def test_get_auth_headers(self, _):
        """
        Test auth headers are returned in required format
        """
        headers = {
            "Authorization": "Bearer Test token",
            "Content-Type": "application/json"
        }
        self.assertEqual(headers, get_auth_headers(self.configuration))

    def test_create_inapp_purchase(self, _):
        """
        Test create in app product call and its exception working properly.
        """

        with mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.post') as post_call:
            post_call.return_value.status_code = 201
            course = {
                'key': 'test',
                'name': 'test',
                'price': '123'
            }
            headers = get_auth_headers(self.configuration)
            create_inapp_purchase(course, 'test.sku', '123', headers)
            create_url = 'https://api.appstoreconnect.apple.com/v2/inAppPurchases'
            self.assertEqual(post_call.call_args[0][0], create_url)
            self.assertEqual(post_call.call_args[1]['headers'], headers)
            with self.assertRaises(AppStoreRequestException, msg="Couldn't create inapp purchase id"):
                post_call.return_value.status_code = 500
                create_inapp_purchase(course, 'test.sku', '123', headers)

    def test_localize_inapp_purchase(self, _):
        """
        Test localize in app product call and its exception working properly.
        """
        with mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.post') as post_call:
            post_call.return_value.status_code = 201
            headers = get_auth_headers(self.configuration)
            localize_inapp_purchase('123', headers)
            localize_url = 'https://api.appstoreconnect.apple.com/v1/inAppPurchaseLocalizations'
            self.assertEqual(post_call.call_args[0][0], localize_url)
            self.assertEqual(post_call.call_args[1]['headers'], headers)

            with self.assertRaises(AppStoreRequestException, msg="Couldn't localize purchase"):
                post_call.return_value.status_code = 500
                localize_inapp_purchase('123', headers)

    def test_apply_price_of_inapp_purchase(self, _):
        """
        Test applying price on in app product call and its exception working properly.
        """
        headers = get_auth_headers(self.configuration)
        with mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.post') as post_call, \
                mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.get') as get_call:
            with self.assertRaises(AppStoreRequestException, msg="Couldn't fetch price points"):
                get_call.return_value.status_code = 500
                apply_price_of_inapp_purchase(100, '123', headers)

            get_call.return_value.status_code = 200
            get_call.return_value.json.return_value = {
                'data': [
                    {
                        'id': '1234',
                        'attributes': {
                            'customerPrice': '99'
                        }
                    }
                ]
            }
            with self.assertRaises(AppStoreRequestException, msg="Couldn't find nearest low price point"):
                # Make sure it doesn't select higher price point
                apply_price_of_inapp_purchase(80, '123', headers)

            post_call.return_value.status_code = 201
            apply_price_of_inapp_purchase(100, '123', headers)
            price_url = 'https://api.appstoreconnect.apple.com/v1/inAppPurchasePriceSchedules'
            self.assertEqual(post_call.call_args[0][0], price_url)
            self.assertEqual(post_call.call_args[1]['headers'], headers)

            with self.assertRaises(AppStoreRequestException, msg="Couldn't apply price"):
                post_call.return_value.status_code = 500
                apply_price_of_inapp_purchase(100, '123', headers)

    def test_upload_screenshot_of_inapp_purchase(self, _):
        """
        Test image uploading call for app product and its exception working properly.
        """
        headers = get_auth_headers(self.configuration)
        with mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.post') as post_call, \
                mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.put') as put_call, \
                mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.patch') as patch_call, \
                mock.patch('django.contrib.staticfiles.storage.staticfiles_storage.open'):

            with self.assertRaises(AppStoreRequestException, msg="Couldn't get screenshot url"):
                post_call.return_value.status_code = 500
                upload_screenshot_of_inapp_purchase('100', headers)

            post_call.return_value.status_code = 201
            post_call.return_value.json.return_value = {
                'data': {
                    'id': '1234',
                    'attributes': {
                        'uploadOperations': [
                            {'url': 'https://image-url.com'}
                        ]
                    }
                }
            }

            with self.assertRaises(AppStoreRequestException, msg="Couldn't upload screenshot"):
                # Make sure it doesn't select higher price point
                upload_screenshot_of_inapp_purchase('123', headers)

            put_call.return_value.status_code = 200

            with self.assertRaises(AppStoreRequestException, msg="Couldn't finalize screenshot"):
                # Make sure it doesn't select higher price point
                upload_screenshot_of_inapp_purchase('123', headers)

            patch_call.return_value.status_code = 200

            upload_screenshot_of_inapp_purchase('123', headers)
            img_url = 'https://api.appstoreconnect.apple.com/v1/inAppPurchaseAppStoreReviewScreenshots'
            self.assertEqual(post_call.call_args[0][0], img_url)
            self.assertEqual(post_call.call_args[1]['headers'], headers)

            self.assertEqual(put_call.call_args[0][0], 'https://image-url.com')
            img_headers = headers.copy()
            img_headers['Content-Type'] = 'image/png'
            self.assertEqual(put_call.call_args[1]['headers'], img_headers)

            img_patch_url = 'https://api.appstoreconnect.apple.com/v1/inAppPurchaseAppStoreReviewScreenshots/1234'
            self.assertEqual(patch_call.call_args[0][0], img_patch_url)
            self.assertEqual(patch_call.call_args[1]['headers'], headers)

    def test_set_territories_of_in_app_purchase(self, _):
        """
        Test applying price on in app product call and its exception working properly.
        """
        headers = get_auth_headers(self.configuration)
        with mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.post') as post_call, \
                mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.get') as get_call:
            with self.assertRaises(AppStoreRequestException, msg="Couldn't fetch territories"):
                get_call.return_value.status_code = 500
                set_territories_of_in_app_purchase('100', headers)

            get_call.return_value.status_code = 200
            get_call.return_value.json.return_value = {
                "data": [
                    {
                        "type": "territories",
                        "id": "AFG",
                        "attributes": {
                            "currency": "USD"
                        },
                        "links": {
                            "self": "https://api.appstoreconnect.apple.com/v1/territories/AFG"
                        }
                    },
                    {
                        "type": "territories",
                        "id": "AGO",
                        "attributes": {
                            "currency": "USD"
                        },
                        "links": {
                            "self": "https://api.appstoreconnect.apple.com/v1/territories/AGO"
                        }
                    }
                ]
            }
            with self.assertRaises(AppStoreRequestException, msg="Couldn't modify territories of inapp purchase"):
                post_call.return_value.status_code = 500
                set_territories_of_in_app_purchase('100', headers)

            post_call.return_value.status_code = 201
            set_territories_of_in_app_purchase('100', headers)
            territory_url = 'https://api.appstoreconnect.apple.com/v1/inAppPurchaseAvailabilities'
            self.assertEqual(post_call.call_args[0][0], territory_url)
            self.assertEqual(post_call.call_args[1]['headers'], headers)

    def test_submit_in_app_purchase_for_review(self, _):
        """
        Test submitting in app product call and its exception working properly.
        """
        headers = get_auth_headers(self.configuration)
        with mock.patch('ecommerce.extensions.iap.api.v1.utils.requests.Session.post') as post_call:
            with self.assertRaises(AppStoreRequestException, msg="Couldn't submit purchase"):
                post_call.return_value.status_code = 500
                submit_in_app_purchase_for_review('100', headers)

            post_call.return_value.status_code = 201
            submit_url = 'https://api.appstoreconnect.apple.com/v1/inAppPurchaseSubmissions'
            self.assertEqual(post_call.call_args[0][0], submit_url)
            self.assertEqual(post_call.call_args[1]['headers'], headers)
