""" Tests of the Payment Views. """


import itertools
import json

import ddt
import httpretty
import mock
import responses
from CyberSource.rest import ApiException, RESTResponse
from django.conf import settings
from django.contrib.auth import get_user
from django.test.client import RequestFactory
from django.urls import reverse
from freezegun import freeze_time
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.models import BusinessClient, User
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.basket.utils import (
    basket_add_organization_attribute,
    get_payment_microfrontend_or_basket_url
)
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.core.sdn import SDNClient
from ecommerce.extensions.payment.exceptions import InvalidBasketError, InvalidSignatureError
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.tests.mixins import (
    CybersourceMixin,
    CybersourceNotificationTestsMixin,
    CyberSourceRESTAPIMixin
)
from ecommerce.extensions.payment.views.cybersource import CybersourceInterstitialView
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')
Source = get_model('payment', 'Source')

post_checkout = get_class('checkout.signals', 'post_checkout')


class LoginMixin:
    def setUp(self):
        super(LoginMixin, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)


@ddt.ddt
@httpretty.activate
class CybersourceAuthorizeViewTests(CyberSourceRESTAPIMixin, TestCase):
    path = reverse('cybersource:authorize')
    CYBERSOURCE_VIEW_LOGGER_NAME = 'ecommerce.extensions.payment.views.cybersource'

    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.pending_responses = []

        def next_response(*args, **kwargs):  # pylint: disable=unused-argument
            response = self.pending_responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        request_patcher = mock.patch(
            'CyberSource.api_client.ApiClient.request',
            side_effect=next_response
        )
        self.mock_cybersource_request = request_patcher.start()
        self.addCleanup(request_patcher.stop)

        jwt_patcher = mock.patch('ecommerce.extensions.payment.processors.cybersource.jwt', name="jwt")
        self.mock_jwt = jwt_patcher.start()
        self.mock_jwt.decode.return_value = {
            'data': {'number': 'xxxx xxxx xxxx 1111'}
        }
        self.addCleanup(jwt_patcher.stop)

        capture_context_patcher = mock.patch(
            'ecommerce.extensions.payment.processors.cybersource.CybersourceREST._unexpired_capture_contexts',
            # pylint: disable=line-too-long
            return_value=[
                (
                    {
                        "keyId": "eyJraWQiOiIzZyIsImFsZyI6IlJTMjU2In0.eyJmbHgiOnsicGF0aCI6Ii9mbGV4L3YyL3Rva2VucyIsImRhdGEiOiJENU9tMHhEUmNVL2x4RS9HdVdJYm9oQUFFR0VZdnNVcGY1Q0FST1lFcXcwSGp4L056NWkxZTV1Z2hCNklHV3hUdFAvNXBWQUdNSzQ5VFJyRkh4RGZBZjVwN29Ga2tWcTVEeUV5YVgzOXhuUThrejRcdTAwM2QiLCJvcmlnaW4iOiJodHRwczovL3Rlc3RmbGV4LmN5YmVyc291cmNlLmNvbSIsImp3ayI6eyJrdHkiOiJSU0EiLCJlIjoiQVFBQiIsInVzZSI6ImVuYyIsIm4iOiJsMjVlMmNGVERPVVRJc28zbHg2ai1nUWRlekg3TWhpWC01SHM5TmhtS1NpVnNqanRXQmFtMGh5WlUzbVpRUTMwb2FVUE1GalIyOUtPSW43S2MzM2RxeWc2M3NEV29hd0VWTTNGamcwVVVBYnp4dXk0T1gtaGxOQVRUd25UVkR3Z2xwa2g4N0x0V0h4Z28telU2Qjd6Zno4d0xVZDA0d3VYb05oTHZKNENLVlJvTG53UG9hMnlxWkhFMi11Sks0UXNVNGtsV05VY25fNjRWNy1QTE9YeTBxWjd6a1ppb1ZWaDVDQWRlTTdFYm5lOG9FY0RfQlJ2OW9uWlhYUllSUWt0OV9VMGpKWlVVVV9ieEtKS20weHRKRlFzUW4tOWp6b1cyMVJtUWhFN19XT3hWNUc4b28wNU56MnJubGx0NFRaaWJhMWhWc2xmaVY3cUZGbkt6aXFxaXciLCJraWQiOiIwN2d1WEp1R1Y5NWxsdWdTZUJ0alZoWjkwMnVQY3c0cyJ9fSwiY3R4IjpbeyJkYXRhIjp7InRhcmdldE9yaWdpbnMiOlsiaHR0cHM6Ly93d3cubWVyY2hhbnQuY29tIiwiaHR0cHM6Ly9zb21lLm90aGVyLnBhcmVudC5jb20iXSwibWZPcmlnaW4iOiJodHRwczovL3Rlc3RmbGV4LmN5YmVyc291cmNlLmNvbSJ9LCJ0eXBlIjoibWYtMC4xMS4wIn1dLCJpc3MiOiJGbGV4IEFQSSIsImV4cCI6MTU4NTE0OTA4MywiaWF0IjoxNTg1MTQ4MTgzLCJqdGkiOiJHTnBJNzU2a2JTd1FZTm9zIn0.QJHfV4BsXmAs4YcPMibVxsrmMPdlyNkpdPvID_7qhoYcPBjXI5Yu_Ghj7OWWaH2vYr4JseJvFlhfs9WQndcFD9lEO9qEX3f0ZdxENmwSPAwvqGJ2m5_Dgln29qd0-0jp_bCLbFWL8v_ftSu6IiIsTBghYt_zI8QE0Uw_lmMP7Uo7BcfHXELY8UhCyJa1MOytSdtVIdqHPH4yX_VLT2DtFLynQEIFRmNnd_WRhuAzZIS9Gp41Zc_Fb9T6R6j8d77atKI1KY6sdNA5OSksfr2Qboi3-AjM7BRUQUprB_HzMcbTinmbYCgPo3POUeB1dqcLvpGAelj1Ooc5i5U9Q-AG4Q",
                        "der": None,
                        "jwk": None
                    }, {
                        "flx": {
                            "path": "/flex/v2/tokens",
                            "data": "D5Om0xDRcU/lxE/GuWIbohAAEGEYvsUpf5CAROYEqw0Hjx/Nz5i1e5ughB6IGWxTtP/5pVAGMK49TRrFHxDfAf5p7oFkkVq5DyEyaX39xnQ8kz4=",
                            "origin": "https://testflex.cybersource.com",
                            "jwk": {
                                "kty": "RSA",
                                "e": "AQAB",
                                "use": "enc",
                                "n": "l25e2cFTDOUTIso3lx6j-gQdezH7MhiX-5Hs9NhmKSiVsjjtWBam0hyZU3mZQQ30oaUPMFjR29KOIn7Kc33dqyg63sDWoawEVM3Fjg0UUAbzxuy4OX-hlNATTwnTVDwglpkh87LtWHxgo-zU6B7zfz8wLUd04wuXoNhLvJ4CKVRoLnwPoa2yqZHE2-uJK4QsU4klWNUcn_64V7-PLOXy0qZ7zkZioVVh5CAdeM7Ebne8oEcD_BRv9onZXXRYRQkt9_U0jJZUUU_bxKJKm0xtJFQsQn-9jzoW21RmQhE7_WOxV5G8oo05Nz2rnllt4TZiba1hVslfiV7qFFnKziqqiw",
                                "kid": "07guXJuGV95llugSeBtjVhZ902uPcw4s"
                            }
                        },
                        "ctx": [
                            {
                                "data": {
                                    "targetOrigins": [
                                        "https://www.merchant.com",
                                        "https://some.other.parent.com"
                                    ],
                                    "mfOrigin": "https://testflex.cybersource.com"
                                },
                                "type": "mf-0.11.0"
                            }
                        ],
                        "iss": "Flex API",
                        "exp": 1568983443,
                        "iat": 1568982543,
                        "jti": "GNpI756kbSwQYNos"
                    }
                )
            ]
            # pylint: enable=line-too-long
        )
        self.mock_unexpired_capture_contexts = capture_context_patcher.start()
        self.addCleanup(capture_context_patcher.stop)

        sdn_patcher = mock.patch.object(SDNClient, 'search', return_value={'total': 0})
        sdn_patcher.start()
        self.addCleanup(sdn_patcher.stop)

        self.mock_access_token_response()

    def _create_valid_basket(self):
        """ Creates a Basket ready for checkout. """
        basket = create_basket(owner=self.user, site=self.site)
        basket.strategy = Selector().strategy()
        basket.thaw()
        return basket

    def _assert_basket_error(self, basket_id, error_msg):
        response = self.client.post(self.path, self._generate_data(basket_id))
        self.assertEqual(response.status_code, 400)
        expected = {
            'error': error_msg,
            'field_errors': {'basket': error_msg}
        }
        self.assertDictEqual(response.json(), expected)

    def _generate_data(self, basket_id):
        country = factories.CountryFactory(iso_3166_1_a2='US', printable_name="United States")
        return {
            'basket': basket_id,
            'first_name': 'Test',
            'last_name': 'User',
            'address_line1': '141 Portland Ave.',
            'address_line2': 'Floor 9',
            'city': 'Cambridge',
            'state': 'MA',
            'postal_code': '02139',
            'country': country.iso_3166_1_a2,
            'payment_token': 'eyJraWQiOiIwOFJxdVc1MjVMdnNhb2g2ck41aE1saExUQ1NKaE1iNyIsImFsZyI6IlJTMjU2In0.eyJkYXRhIjp7ImV4cGlyYXRpb25ZZWFyIjoiMjAyMiIsIm51bWJlciI6IjQxMTExMVhYWFhYWDExMTEiLCJleHBpcmF0aW9uTW9udGgiOiIwMSIsInR5cGUiOiIwMDEifSwiaXNzIjoiRmxleC8wOCIsImV4cCI6MTYwMjg2NDQyMiwidHlwZSI6Im1mLTAuMTEuMCIsImlhdCI6MTYwMjg2MzUyMiwianRpIjoiMUUzUUlKSFBDMEI0R0JWM0hSVkFBVDdMTlc3WlhIQU9QUE5ZTk44UEpYQVIxT0g4TlNIVDVGODlDNTI2MTA2NSJ9.VYO3omXc1kyg7LejBYgxYCvkseDc3CVR-vuN65Tr_GNeUo9nJwmaGMC0OgJevecRxdCVkma-S1pNGL1USKPnuuKoM0FYpasfbGXKoR6o1KscB65Cbr_1D4UiRe2j1EhNsYsm8xI_mRHtTVhseT0hY0f8y-90gnRcCN7JUCHzdb4ArS4imMccF9nJ3NHd-24FGeB7qjp_w4UPSO53g7eLVHqaT09n4rmJUaIYFyfXed48rIcKf1XbMF-jVnPsCaD3iLxPY-I27PAyErkZbMOdENqXkPthgQ0pHGpu97v0FjipCOSK2C3dk-PrB1ZQBLtcHiVSJcQvNxLhdOa8-QvRKg',  # pylint: disable=line-too-long
        }

    def _prep_request_success(self, data, status=200, reason='OK'):
        self.pending_responses.append(
            mock.Mock(
                spec=RESTResponse,
                resp=None,
                status=status,
                reason=reason,
                # This response has been pruned to only the needed data.
                data=self.convertToCybersourceWireFormat(data)
            )
        )

    def _prep_request_invalid(self, data, request_id, status=400, reason='BAD REQUEST'):

        self.pending_responses.append(
            ApiException(
                http_resp=mock.Mock(
                    spec=RESTResponse,
                    resp=None,
                    status=status,
                    reason=reason,
                    getheaders=mock.Mock(return_value={'v-c-correlation-id': request_id}),
                    # This response has been pruned to only the needed data.
                    data=self.convertToCybersourceWireFormat(data)
                )
            )
        )

    def assert_basket_retrieval_error(self, basket_id):
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
        return self._assert_basket_error(basket_id, error_msg)

    def test_login_required(self):
        """ Verify the view returns a 401 for unauthorized users. """
        self.client.logout()
        response = self.client.post(self.path)
        assert response.status_code == 401

    @ddt.data('get', 'put', 'patch', 'head')
    def test_invalid_methods(self, method):
        """ Verify the view only supports the POST and OPTION HTTP methods."""
        response = getattr(self.client, method)(self.path)
        assert response.status_code == 405

    def test_missing_basket(self):
        """ Verify the view returns an HTTP 400 status if the basket is missing. """
        self.assert_basket_retrieval_error(9999)

    def test_mismatched_basket_owner(self):
        """ Verify the view returns an HTTP 400 status if the posted basket does not belong to the requesting user. """
        basket = factories.BasketFactory()
        self.assert_basket_retrieval_error(basket.id)

        basket = factories.BasketFactory(owner=self.create_user())
        self.assert_basket_retrieval_error(basket.id)

    @ddt.data(Basket.MERGED, Basket.SAVED, Basket.FROZEN, Basket.SUBMITTED)
    def test_invalid_basket_status(self, status):
        """ Verify the view returns an HTTP 400 status if the basket is in an invalid state. """
        basket = factories.BasketFactory(owner=self.user, status=status)
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
        self._assert_basket_error(basket.id, error_msg)

    def test_sdn_check_match(self):
        """Verify the endpoint returns an sdn check failure if the sdn check finds a hit."""
        self.site.siteconfiguration.enable_sdn_check = True
        self.site.siteconfiguration.save()

        basket_id = self._create_valid_basket().id
        data = self._generate_data(basket_id)
        expected_response = {'error': 'There was an error submitting the basket', 'sdn_check_failure': {'hit_count': 1}}
        logger_name = self.CYBERSOURCE_VIEW_LOGGER_NAME

        with mock.patch.object(SDNClient, 'search', return_value={'total': 1}) as sdn_validator_mock:
            with mock.patch.object(User, 'deactivate_account', return_value=True):
                with LogCapture(logger_name) as cybersource_logger:
                    response = self.client.post(self.path, data)
                    self.assertTrue(sdn_validator_mock.called)
                    self.assertEqual(response.json(), expected_response)
                    self.assertEqual(response.status_code, 403)
                    cybersource_logger.check_present(
                        (
                            logger_name,
                            'INFO',
                            'SDNCheck function called for basket [{}]. It received 1 hit(s).'.format(basket_id)
                        ),
                    )
                    # Make sure user is logged out
                    self.assertEqual(get_user(self.client).is_authenticated, False)

    @freeze_time('2016-01-01')
    def test_valid_request(self):
        """ Verify the view completes the transaction if the request is valid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        order_number = OrderNumberGenerator().order_number_from_basket_id(
            self.site.siteconfiguration.partner,
            basket.id,
        )
        # This response has been pruned to only the needed data.
        self._prep_request_success(
            """{"links":{"_self":{"href":"/pts/v2/payments/6031827608526961004260","method":"GET"}},"id":"6031827608526961004260","submit_time_utc":"2020-10-20T08:32:44Z","status":"AUTHORIZED","client_reference_information":{"code":"%s"},"processor_information":{"approval_code":"307640","transaction_id":"380294307616695","network_transaction_id":"380294307616695","response_code":"000","avs":{"code":"G","code_raw":"G"},"card_verification":{"result_code":"M","result_code_raw":"M"},"consumer_authentication_response":{"code":"99"}},"payment_information":{"tokenized_card":{"type":"001"},"account_features":{"category":"F"}},"order_information":{"amount_details":{"total_amount":"5.00","authorized_amount":"5.00","currency":"USD"}}}""" % order_number  # pylint: disable=line-too-long
        )
        response = self.client.post(self.path, data)

        assert response.status_code == 201
        assert response['content-type'] == JSON
        assert json.loads(response.content)['receipt_page_url'] == get_receipt_page_url(
            self.site.siteconfiguration,
            order_number=order_number,
            disable_back_button=True,
        )

        # Ensure the basket is Submitted
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.SUBMITTED)

    def test_duplicate_payment(self):
        """ Verify the view errors as expected if there is a duplicate payment attempt after a successful payment. """
        # This unit test describes the current state of the code, but I'm not sure if there are other
        # situations that would result in a duplicate payment that we should handle differently.

        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        order_number = OrderNumberGenerator().order_number_from_basket_id(
            self.site.siteconfiguration.partner,
            basket.id,
        )
        # This response has been pruned to only the needed data.
        self._prep_request_success(
            """{"id":"6028635251536131304003","status":"AUTHORIZED","client_reference_information":{"code":"%s"},"processor_information":{"approval_code":"831000","transaction_id":"558196000003814","network_transaction_id":"558196000003814","card_verification":{"result_code":"3"}},"payment_information":{"tokenized_card":{"type":"001"},"account_features":{"category":"A"}},"order_information":{"amount_details":{"total_amount":"99.00","authorized_amount":"99.00","currency":"USD"}}}""" % order_number  # pylint: disable=line-too-long
        )
        response = self.client.post(self.path, data)

        assert response.status_code == 201
        assert response['content-type'] == JSON
        assert json.loads(response.content)['receipt_page_url'] == get_receipt_page_url(
            self.site.siteconfiguration,
            order_number=order_number,
            disable_back_button=True,
        )

        # Ensure the basket is Submitted
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.SUBMITTED)

        # This response has been pruned to only the needed data.
        self._prep_request_invalid(
            """{"submitTimeUtc":"2020-09-30T18:53:23Z","status":"INVALID_REQUEST","reason":"DUPLICATE_REQUEST","message":"Declined - The\u00a0merchantReferenceCode\u00a0sent with this authorization request matches the merchantReferenceCode of another authorization request that you sent in the last 15 minutes."}""",  # pylint: disable=line-too-long
            '6028635251536131304003'
        )
        response = self.client.post(self.path, data)

        # The original basket is frozen, and the new basket is empty, so currentyl this triggers an error response
        assert response.status_code == 400
        assert response['content-type'] == JSON
        assert json.loads(response.content) == {
            'error': 'There was a problem retrieving your basket. Refresh the page to try again.',
            'field_errors': {
                'basket': 'There was a problem retrieving your basket. Refresh the page to try again.'
            }
        }

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk + 1)
        self.assertEqual(basket.status, Basket.OPEN)

    @freeze_time('2016-01-01')
    def test_decline(self):
        """ Verify the view reports an error if the transaction is only authorized pending review. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        order_number = OrderNumberGenerator().order_number_from_basket_id(
            self.site.siteconfiguration.partner,
            basket.id,
        )
        # This response has been pruned to only the needed data.
        self._prep_request_success(
            """{"links":{"_self":{"href":"/pts/v2/payments/6021683934456376603262","method":"GET"}},"id":"6021683934456376603262","status":"DECLINED","error_information":{"reason":"PROCESSOR_DECLINED","message":"Decline - General decline of the card. No other information provided by the issuing bank."},"client_reference_information":{"code":"%s"},"processor_information":{"transaction_id":"460282531937765","network_transaction_id":"460282531937765","response_code":"005","avs":{"code":"D","code_raw":"D"},"card_verification":{"result_code":"M","result_code_raw":"M"}},"payment_information":{"account_features":{"category":"F"}}}""" % order_number  # pylint: disable=line-too-long
        )
        response = self.client.post(self.path, data)

        assert response.status_code == 400
        assert response['content-type'] == JSON

        request = RequestFactory(SERVER_NAME='testserver.fake').post(self.path, data)
        request.site = self.site
        assert json.loads(response.content)['redirectTo'] == get_payment_microfrontend_or_basket_url(request)

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.MERGED)
        assert Basket.objects.count() == 2

    @freeze_time('2016-01-01')
    def test_authorized_pending_review_request(self):
        """ Verify the view reports an error if the transaction is only authorized pending review. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        order_number = OrderNumberGenerator().order_number_from_basket_id(
            self.site.siteconfiguration.partner,
            basket.id,
        )
        # This response has been pruned to only the needed data.
        self._prep_request_success(
            """{"links":{"_self":{"href":"/pts/v2/payments/6038898237296087603031","method":"GET"}},"id":"6038898237296087603031","submit_time_utc":"2020-10-28T12:57:04Z","status":"AUTHORIZED_PENDING_REVIEW","error_information":{"reason":"AVS_FAILED","message":"Soft Decline - The authorization request was approved by the issuing bank but declined by CyberSource because it did not pass the Address Verification Service (AVS) check."},"client_reference_information":{"code":"%s"},"processor_information":{"approval_code":"028252","transaction_id":"580302466249046","network_transaction_id":"580302466249046","response_code":"000","avs":{"code":"N","code_raw":"N"},"card_verification":{"result_code":"M","result_code_raw":"M"}},"payment_information":{"account_features":{"category":"C"}},"order_information":{"amount_details":{"authorized_amount":"25.00","currency":"USD"}}}""" % order_number  # pylint: disable=line-too-long
        )
        self._prep_request_success(
            """{"links":{"_self":{"href":"/pts/v2/payments/6038898237296087603031/reversals","method":"GET"}},"id":"6038898237296087603031","submit_time_utc":"2020-10-28T12:57:04Z","status":"REVERSED","reversal_amount_details":{"original_transaction_amount":"25.00", "reversed_amount":"25.00","currency":"USD"}}"""  # pylint: disable=line-too-long
        )
        response = self.client.post(self.path, data)

        assert response.status_code == 400
        assert response['content-type'] == JSON

        request = RequestFactory(SERVER_NAME='testserver.fake').post(self.path, data)
        request.site = self.site
        assert json.loads(response.content)['redirectTo'] == get_payment_microfrontend_or_basket_url(request)

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.MERGED)
        assert Basket.objects.count() == 2

        # Ensure that 2 requests were sent to cybersource
        assert self.mock_cybersource_request.call_count == 2

        # Ensure that 2 requests and 2 responses were recorded as PaymentProcessorResponses
        assert PaymentProcessorResponse.objects.all().count() == 4

    @freeze_time('2016-01-01')
    def test_authorized_pending_review_request_reversal_failed(self):
        """ Verify the view reports an error if the transaction is only authorized pending review. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        order_number = OrderNumberGenerator().order_number_from_basket_id(
            self.site.siteconfiguration.partner,
            basket.id,
        )
        # This response has been pruned to only the needed data.
        self._prep_request_success(
            """{"links":{"_self":{"href":"/pts/v2/payments/6038898237296087603031","method":"GET"}},"id":"6038898237296087603031","submit_time_utc":"2020-10-28T12:57:04Z","status":"AUTHORIZED_PENDING_REVIEW","error_information":{"reason":"AVS_FAILED","message":"Soft Decline - The authorization request was approved by the issuing bank but declined by CyberSource because it did not pass the Address Verification Service (AVS) check."},"client_reference_information":{"code":"%s"},"processor_information":{"approval_code":"028252","transaction_id":"580302466249046","network_transaction_id":"580302466249046","response_code":"000","avs":{"code":"N","code_raw":"N"},"card_verification":{"result_code":"M","result_code_raw":"M"}},"payment_information":{"account_features":{"category":"C"}},"order_information":{"amount_details":{"authorized_amount":"25.00","currency":"USD"}}}""" % order_number  # pylint: disable=line-too-long
        )
        self._prep_request_invalid(
            """{"submitTimeUtc":"2020-09-30T18:53:23Z","status":"INVALID_REQUEST","reason":"DUPLICATE_REQUEST","message":"Declined - The\u00a0merchantReferenceCode\u00a0sent with this authorization request matches the merchantReferenceCode of another authorization request that you sent in the last 15 minutes."}""",  # pylint: disable=line-too-long
            '6038898237296087603031'
        )

        response = self.client.post(self.path, data)

        assert response.status_code == 400
        assert response['content-type'] == JSON

        request = RequestFactory(SERVER_NAME='testserver.fake').post(self.path, data)
        request.site = self.site
        assert json.loads(response.content)['redirectTo'] == get_payment_microfrontend_or_basket_url(request)

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.MERGED)
        assert Basket.objects.count() == 2

        # Ensure that 2 requests were sent to cybersource
        assert self.mock_cybersource_request.call_count == 2

        # Ensure that 2 requests and 2 responses were recorded as PaymentProcessorResponses
        assert PaymentProcessorResponse.objects.all().count() == 4

    def test_invalid_card_type(self):
        """ Verify the view redirects to the receipt page if the payment is made with an invalid card type. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        # This response has been pruned to only the needed data.
        self._prep_request_invalid(
            """{"submitTimeUtc":"2020-10-20T15:44:23Z","status":"INVALID_REQUEST","reason":"CARD_TYPE_NOT_ACCEPTED","message":"Decline - The card type is not accepted by the payment processor."}""",  # pylint: disable=line-too-long
            '6028635251536131304003'
        )
        response = self.client.post(self.path, data)

        assert response.status_code == 400
        assert response['content-type'] == JSON
        assert json.loads(response.content) == {}

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.FROZEN)

    def test_field_error(self):
        """ Verify the view responds with a JSON object containing fields with errors, when input is invalid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        field = 'first_name'
        del data[field]

        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['content-type'], JSON)

        errors = response.json()['field_errors']
        self.assertIn(field, errors)


@ddt.ddt
class CybersourceSubmitViewTests(CybersourceMixin, TestCase):
    path = reverse('cybersource:submit')
    CYBERSOURCE_VIEW_LOGGER_NAME = 'ecommerce.extensions.payment.views.cybersource'

    def setUp(self):
        super(CybersourceSubmitViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def _generate_data(self, basket_id):
        country = factories.CountryFactory(iso_3166_1_a2='US', printable_name="United States")
        return {
            'basket': basket_id,
            'first_name': 'Test',
            'last_name': 'User',
            'address_line1': '141 Portland Ave.',
            'address_line2': 'Floor 9',
            'city': 'Cambridge',
            'state': 'MA',
            'postal_code': '02139',
            'country': country.iso_3166_1_a2,
        }

    def _create_valid_basket(self):
        """ Creates a Basket ready for checkout. """
        basket = create_basket(owner=self.user, site=self.site)
        basket.strategy = Selector().strategy()
        basket.thaw()
        return basket

    def assert_basket_retrieval_error(self, basket_id):
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
        return self._assert_basket_error(basket_id, error_msg)

    def test_login_required(self):
        """ Verify the view redirects anonymous users to the login page. """
        self.client.logout()
        response = self.client.post(self.path)
        expected_url = '{base}?next={path}'.format(base=reverse(settings.LOGIN_URL),
                                                   path=self.path)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @ddt.data('get', 'put', 'patch', 'head')
    def test_invalid_methods(self, method):
        """ Verify the view only supports the POST and OPTION HTTP methods."""
        response = getattr(self.client, method)(self.path)
        self.assertEqual(response.status_code, 405)

    def _assert_basket_error(self, basket_id, error_msg):
        response = self.client.post(self.path, self._generate_data(basket_id))
        self.assertEqual(response.status_code, 400)
        expected = {
            'error': error_msg,
            'field_errors': {'basket': error_msg}
        }
        self.assertDictEqual(response.json(), expected)

    def test_missing_basket(self):
        """ Verify the view returns an HTTP 400 status if the basket is missing. """
        self.assert_basket_retrieval_error(9999)

    def test_mismatched_basket_owner(self):
        """ Verify the view returns an HTTP 400 status if the posted basket does not belong to the requesting user. """
        basket = factories.BasketFactory()
        self.assert_basket_retrieval_error(basket.id)

        basket = factories.BasketFactory(owner=self.create_user())
        self.assert_basket_retrieval_error(basket.id)

    @ddt.data(Basket.MERGED, Basket.SAVED, Basket.FROZEN, Basket.SUBMITTED)
    def test_invalid_basket_status(self, status):
        """ Verify the view returns an HTTP 400 status if the basket is in an invalid state. """
        basket = factories.BasketFactory(owner=self.user, status=status)
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
        self._assert_basket_error(basket.id, error_msg)

    def test_sdn_check_match(self):
        """Verify the endpoint returns an sdn check failure if the sdn check finds a hit."""
        self.site.siteconfiguration.enable_sdn_check = True
        self.site.siteconfiguration.save()

        basket_id = self._create_valid_basket().id
        data = self._generate_data(basket_id)
        expected_response = {'error': 'There was an error submitting the basket', 'sdn_check_failure': {'hit_count': 1}}
        logger_name = self.CYBERSOURCE_VIEW_LOGGER_NAME

        with mock.patch.object(SDNClient, 'search', return_value={'total': 1}) as sdn_validator_mock:
            with mock.patch.object(User, 'deactivate_account', return_value=True):
                with LogCapture(logger_name) as cybersource_logger:
                    response = self.client.post(self.path, data)
                    self.assertTrue(sdn_validator_mock.called)
                    self.assertEqual(response.json(), expected_response)
                    self.assertEqual(response.status_code, 403)
                    cybersource_logger.check_present(
                        (
                            logger_name,
                            'INFO',
                            'SDNCheck function called for basket [{}]. It received 1 hit(s).'.format(basket_id)
                        ),
                    )
                    # Make sure user is logged out
                    self.assertEqual(get_user(self.client).is_authenticated, False)

    @freeze_time('2016-01-01')
    def test_valid_request(self):
        """ Verify the view returns the CyberSource parameters if the request is valid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], JSON)

        actual = response.json()['form_fields']
        transaction_uuid = actual['transaction_uuid']
        extra_parameters = {
            'payment_method': 'card',
            'unsigned_field_names': 'card_cvn,card_expiry_date,card_number,card_type',
            'bill_to_email': self.user.email,
            'device_fingerprint_id': self.client.session.session_key,
            'bill_to_address_city': data['city'],
            'bill_to_address_country': data['country'],
            'bill_to_address_line1': data['address_line1'],
            'bill_to_address_line2': data['address_line2'],
            'bill_to_address_postal_code': data['postal_code'],
            'bill_to_address_state': data['state'],
            'bill_to_forename': data['first_name'],
            'bill_to_surname': data['last_name'],
        }

        expected = self.get_expected_transaction_parameters(
            basket,
            transaction_uuid,
            use_sop_profile=True,
            extra_parameters=extra_parameters
        )
        self.assertDictEqual(actual, expected)

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.FROZEN)

    def test_field_error(self):
        """ Verify the view responds with a JSON object containing fields with errors, when input is invalid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        field = 'first_name'
        del data[field]

        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['content-type'], JSON)

        errors = response.json()['field_errors']
        self.assertIn(field, errors)


class CybersourceSubmitAPIViewTests(CybersourceSubmitViewTests):
    path = reverse('cybersource:api_submit')

    def setUp(self):  # pylint: disable=useless-super-delegation
        super(CybersourceSubmitAPIViewTests, self).setUp()

    def test_login_required(self):
        """ Verify the view returns 401 for unauthenticated users. """
        self.client.logout()
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 401)

    @freeze_time('2016-01-01')
    def test_valid_request(self):
        """ Verify the view returns the CyberSource parameters if the request is valid. """
        super(CybersourceSubmitAPIViewTests, self).test_valid_request()


@ddt.ddt
class CybersourceInterstitialViewTests(CybersourceNotificationTestsMixin, TestCase):
    """ Test interstitial view for Cybersource Payments. """
    path = reverse('cybersource:redirect')
    view = CybersourceInterstitialView

    @ddt.data(
        ('12345678-1234-1234-1234-123456789abc', 1),
        (None, 0)
    )
    @ddt.unpack
    def test_payment_declined(self, bundle, bundle_attr_count):
        """
        Verify that the user is redirected to the basket summary page when their
        payment is declined.
        """
        # Basket merging clears lines on the old basket. We need to take a snapshot
        # of lines currently on this basket before it gets merged with a new basket.
        old_lines = list(self.basket.lines.all())
        if bundle:
            BasketAttribute.objects.update_or_create(
                basket=self.basket,
                attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
                value_text=bundle
            )

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )

        logger_name = self.CYBERSOURCE_VIEW_LOGGER_NAME
        with mock.patch.object(self.view, 'validate_order_completion', side_effect=TransactionDeclined):
            with LogCapture(logger_name) as cybersource_logger:
                response = self.client.post(self.path, notification)

                self.assertRedirects(
                    response,
                    self.get_full_url(path=reverse('basket:summary')),
                    status_code=302,
                    fetch_redirect_response=False
                )

                new_basket = Basket.objects.get(status='Open')
                merged_basket_count = Basket.objects.filter(status='Merged').count()
                new_basket_bundle_count = BasketAttribute.objects.filter(
                    basket=new_basket,
                    attribute_type=BasketAttributeType.objects.get(name='bundle_identifier')
                ).count()

                self.assertEqual(list(new_basket.lines.all()), old_lines)
                self.assertEqual(merged_basket_count, 1)
                self.assertEqual(new_basket_bundle_count, bundle_attr_count)

                log_msg = 'Created new basket [{}] from old basket [{}] for declined transaction with bundle [{}].'
                cybersource_logger.check_present(
                    (
                        logger_name,
                        'INFO',
                        log_msg.format(
                            new_basket.id,
                            self.basket.id,
                            bundle
                        )
                    ),
                )

    @ddt.data(InvalidSignatureError, InvalidBasketError, Exception)
    def test_invalid_payment_error(self, error_class):
        """
        Verify that the view redirects to the payment error page when an error
        occurs while processing a payment notification.
        """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(self.view, 'validate_order_completion', side_effect=error_class):
            response = self.client.post(self.path, notification)
            self.assertRedirects(response, self.get_full_url(reverse('payment_error')))

    def test_payment_error_context(self):
        response = self.client.get(reverse('payment_error'))
        self.assertDictContainsSubset(
            {
                'dashboard_url': get_lms_url(),
                'payment_support_email': self.site.siteconfiguration.payment_support_email
            },
            response.context
        )

    def test_successful_order(self):
        """ Verify the view redirects to the Receipt page when the Order has been successfully placed. """
        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        response = self.client.post(self.path, notification)
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())
        self.assertEqual(response.status_code, 302)

    def test_successful_order_for_bulk_purchase(self):
        """
        Verify the view redirects to the Receipt page when the Order has been
        successfully placed for bulk purchase and also that the order is linked
        to the provided business client.
        """
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)

        course = CourseFactory()
        course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        self.basket = create_basket(owner=self.user, site=self.site)
        self.basket.add_product(enrollment_code, quantity=1)

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        request_data = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        request_data.update({'organization': 'Dummy Business Client'})
        request_data.update({PURCHASER_BEHALF_ATTRIBUTE: "False"})
        # Manually add organization and purchaser attributes on the basket for testing
        basket_add_organization_attribute(self.basket, request_data)

        response = self.client.post(self.path, request_data)
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())
        self.assertEqual(response.status_code, 302)

        # Now verify that a new business client has been created and current
        # order is now linked with that client through Invoice model.
        order = Order.objects.filter(basket=self.basket).first()
        business_client = BusinessClient.objects.get(name=request_data['organization'])
        assert Invoice.objects.get(order=order).business_client == business_client

    def test_order_creation_error(self):
        """ Verify the view redirects to the Payment error page when an error occurred during Order creation. """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(self.view, 'create_order', side_effect=Exception):
            response = self.client.post(self.path, notification)
            self.assertRedirects(response, self.get_full_url(path=reverse('payment_error')), status_code=302)

    def test_duplicate_order_attempt_logging(self):
        """
        Verify that attempts at creation of a duplicate order are logged correctly
        """
        prior_order = create_order()
        dummy_request = RequestFactory(SERVER_NAME='testserver.fake').get('')
        dummy_mixin = EdxOrderPlacementMixin()
        dummy_mixin.payment_processor = Cybersource(self.site)

        with LogCapture(self.DUPLICATE_ORDER_LOGGER_NAME) as lc:
            with self.assertRaises(ValueError):
                dummy_mixin.create_order(dummy_request, prior_order.basket, None)
                lc.check(
                    (
                        self.DUPLICATE_ORDER_LOGGER_NAME,
                        'ERROR',
                        self.get_duplicate_order_error_message(payment_processor='Cybersource', order=prior_order)
                    ),
                )

    def test_order_creation_after_duplicate_reference_number_error(self):
        """ Verify view creates the order if there is no existing order in case of DuplicateReferenceNumber """
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
            decision='error',
            reason_code='104',
        )
        response = self.client.post(self.path, notification)
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())
        self.assertEqual(response.status_code, 302)


@ddt.ddt
class ApplePayStartSessionViewTests(LoginMixin, TestCase):
    url = reverse('cybersource:apple_pay:start_session')
    payment_microfrontend_domain = 'payment-mfe.org'

    def _call_to_apple_pay_and_assert_response(self, status, body, request_from_mfe=False, expected_mfe=False):
        url = 'https://apple-pay-gateway.apple.com/paymentservices/startSession'
        body = json.dumps(body)
        responses.add(responses.POST, url, body=body, status=status, content_type=JSON)

        post_data = {'url': url}
        if request_from_mfe:
            post_data.update({'is_payment_microfrontend': True})

        response = self.client.post(self.url, json.dumps(post_data), JSON)
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.content.decode('utf-8'), body)

        expected_domain_name = self.payment_microfrontend_domain if expected_mfe else 'testserver.fake'
        self.assertEqual(
            json.loads(responses.calls[0].request.body.decode('utf-8'))['domainName'],
            expected_domain_name,
        )

    @ddt.data(
        (200, {'foo': 'bar'}),
        (500, {'error': 'Failure!'})
    )
    @ddt.unpack
    @responses.activate
    def test_post(self, status, body):
        """ The view should POST to the given URL and return the response. """
        self._call_to_apple_pay_and_assert_response(status, body)

    @responses.activate
    @ddt.data(*itertools.product((True, False), (True, False)))
    @ddt.unpack
    def test_with_microfrontend(self, request_from_mfe, enable_microfrontend):
        self.site.siteconfiguration.enable_microfrontend_for_basket_page = enable_microfrontend
        self.site.siteconfiguration.payment_microfrontend_url = 'http://{}'.format(self.payment_microfrontend_domain)
        self.site.siteconfiguration.save()

        self._call_to_apple_pay_and_assert_response(
            200,
            {'foo': 'bar'},
            request_from_mfe,
            request_from_mfe and enable_microfrontend,
        )

    def test_post_without_url(self):
        """ The view should return HTTP 400 if no url parameter is posted. """
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'url is required'})


@ddt.ddt
class CybersourceApplePayAuthorizationViewTests(LoginMixin, CybersourceMixin, TestCase):
    url = reverse('cybersource:apple_pay:authorize')

    def generate_post_data(self):
        address = factories.BillingAddressFactory()

        return {
            'billingContact': {
                'addressLines': [
                    address.line1,
                    address.line1
                ],
                'administrativeArea': address.state,
                'country': address.country.printable_name,
                'countryCode': address.country.iso_3166_1_a2,
                'familyName': self.user.last_name,
                'givenName': self.user.first_name,
                'locality': address.line4,
                'postalCode': address.postcode,
            },
            'shippingContact': {
                'emailAddress': self.user.email,
                'familyName': self.user.last_name,
                'givenName': self.user.first_name,
            },
            'token': {
                'paymentData': {
                    'version': 'EC_v1',
                    'data': 'fake-data',
                    'signature': 'fake-signature',
                    'header': {
                        'ephemeralPublicKey': 'fake-key',
                        'publicKeyHash': 'fake-hash',
                        'transactionId': 'abc123'
                    }
                },
                'paymentMethod': {
                    'displayName': 'AmEx 1086',
                    'network': 'AmEx',
                    'type': 'credit'
                },
                'transactionIdentifier': 'DEADBEEF'
            }
        }

    @responses.activate
    def test_post(self):
        """ The view should authorize and settle payment at CyberSource, and create an order. """
        data = self.generate_post_data()
        basket = create_basket(owner=self.user, site=self.site)
        basket.strategy = Selector().strategy()

        self.mock_cybersource_wsdl()
        self.mock_authorization_response(accepted=True)
        response = self.client.post(self.url, json.dumps(data), JSON)

        self.assertEqual(response.status_code, 201)
        PaymentProcessorResponse.objects.get(basket=basket)

        order = Order.objects.all().first()
        total = order.total_incl_tax
        self.assertEqual(response.data, OrderSerializer(order, context={'request': self.request}).data)
        order.payment_events.get(event_type__code='paid', amount=total)
        Source.objects.get(
            source_type__name=Cybersource.NAME, currency=order.currency, amount_allocated=total, amount_debited=total,
            label='Apple Pay')
        PaymentEvent.objects.get(event_type__name=PaymentEventTypeName.PAID, amount=total,
                                 processor_name=Cybersource.NAME)

    @responses.activate
    def test_post_with_rejected_payment(self):
        """ The view should return an error if CyberSource rejects payment. """
        data = self.generate_post_data()
        self.mock_cybersource_wsdl()
        self.mock_authorization_response(accepted=False)
        response = self.client.post(self.url, json.dumps(data), JSON)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data, {'error': 'payment_failed'})

    def test_post_with_invalid_billing_address(self):
        """ The view should return an error if the billing address is invalid. """
        data = self.generate_post_data()
        data['billingContact'] = {}
        response = self.client.post(self.url, json.dumps(data), JSON)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'billing_address_invalid'})

    def test_post_with_invalid_country(self):
        """ The view should log a warning if the country code is invalid. """
        data = self.generate_post_data()
        country_code = 'FAKE'
        data['billingContact']['countryCode'] = country_code

        with mock.patch('ecommerce.extensions.payment.views.cybersource.logger.warning') as mock_logger:
            response = self.client.post(self.url, json.dumps(data), JSON)
            mock_logger.assert_called_once_with('Country matching code [%s] does not exist.', country_code)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'billing_address_invalid'})

    def test_post_without_payment_token(self):
        """ The view should return an error if no payment token is provided. """
        data = self.generate_post_data()
        data['token'] = {}
        response = self.client.post(self.url, json.dumps(data), JSON)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'token_missing'})
