

import json
import logging

import ddt
import mock
from django.test.utils import override_settings
from django.urls import reverse
from testfixtures import LogCapture

from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_BOUNCED
from ecommerce.extensions.offer.models import OfferAssignment, OfferAssignmentEmailAttempt
from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase
from ecommerce.tests.utils import DoesNotExist


@ddt.ddt
class AssignmentEmailStatusTests(TestCase):
    """ Tests for AssignmentEmailStatus API view. """
    path = reverse('api:v2:assignment-email:update_status')

    def setUp(self):
        super(AssignmentEmailStatusTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.data = {
            'offer_assignment_id': 556,
            'send_id': 'XBEn85WnoQJsIhk8',
            'status': 'success'
        }

    def test_authentication_required(self):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 401)

    @ddt.data(
        (
            # Update task exception issue
            {
                'offer_assignment_id': 555,
                'send_id': 'XBEn85WnoQJsIhk6',
                'status': 'success',
            },
            {
                'offer_assignment_id': 555,
                'send_id': 'XBEn85WnoQJsIhk6',
                'status': 'failed',
                'error': 'OfferAssignment matching query does not exist.'
            },
            ("[Offer Assignment] AssignmentEmailStatus update raised: "
             "{}".format(repr(DoesNotExist('OfferAssignment matching query does not exist.')))),
            500,
        ),
        (
            # Unknown status issue
            {
                'offer_assignment_id': 555,
                'send_id': 'XBEn85WnoQJsIhk6',
                'status': 'wrong_status',
            },
            {
                'offer_assignment_id': 555,
                'send_id': 'XBEn85WnoQJsIhk6',
                'status': 'failed',
                'error': 'Incorrect status'
            },
            "[Offer Assignment] AssignmentEmailStatus could not update status for OfferAssignmentId: 555",
            400,
        ),
    )
    @ddt.unpack
    def test_email_status_update_failure(
            self,
            post_data,
            response_data,
            log_data,
            status_code,
    ):
        """
        Verify the endpoint returned the failed status when
        requisite keys are not present in offer_assignment model
        """
        log_name = 'ecommerce.extensions.api.v2.views.assignmentemail'
        with LogCapture(log_name, level=logging.INFO) as log:
            response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        log.check_present(
            (log_name, 'ERROR', log_data),
        )
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, response.json())

    @ddt.data(
        (
            # A valid request.
            {
                'offer_assignment_id': 1,
                'send_id': 'XBEn85WnoQJsIhk7',
                'status': 'success',
            },
            {
                'offer_assignment_id': 1,
                'send_id': 'XBEn85WnoQJsIhk7',
                'status': 'updated',
                'error': ''
            },
            200,
        ),
    )
    @ddt.unpack
    def test_email_status_update_success(
            self,
            post_data,
            response_data,
            status_code,
    ):
        """ Verify the endpoint updated the email status in offer_assignment """
        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=None)
        offer_assignment = factories.OfferAssignmentFactory(
            offer=enterprise_offer,
            code='jfhrmndk554lwre',
            user_email='johndoe@unknown.com',
        )
        post_data['offer_assignment_id'] = offer_assignment.id
        response_data['offer_assignment_id'] = offer_assignment.id
        response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, response.json())
        updated_offer_assignment = OfferAssignment.objects.get(id=offer_assignment.id)
        self.assertEqual(updated_offer_assignment.status, OFFER_ASSIGNED)


@ddt.ddt
class AssignmentEmailBounceTests(TestCase):
    """ Tests for AssignmentEmailBounce API view. """
    path = reverse('api:v2:assignment-email:receive_bounce')
    log_name = 'ecommerce.extensions.api.v2.views.assignmentemail'

    def setUp(self):
        super(AssignmentEmailBounceTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    @ddt.data(
        (
            # Incorrect hash.
            {
                'email': 'blashsdsd@dfsdf.com',
                'send_id': 'WFQKQW5K3LBgi0mk',
                'action': 'hardbounce',
                'api_key': 'abc123',
                'sig': 'incorrect_hash',
            },
            {},
            "[Offer Assignment] AssignmentEmailBounce: Bounce message could not be verified."
            " send_id: WFQKQW5K3LBgi0mk, email: blashsdsd@dfsdf.com, sig: incorrect_hash,"
            " api_key_sailthru: abc123, api_key_local: abc123 ",
            200,
            'top_secret',
        ),
        (
            # Sailthru settings undefined.
            {
                'email': 'blashsdsd@dfsdf.com',
                'send_id': 'WFQKQW5K3LBgi0mk',
                'action': 'hardbounce',
                'api_key': 'abc123',
                'sig': 'e705b3d5964e82c82136cadd68020384',
            },
            {},
            "[Offer Assignment] AssignmentEmailBounce: SAILTHRU Parameters not found",
            200,
            None,
        ),
    )
    @ddt.unpack
    def test_email_status_update_failure(
            self,
            post_data,
            response_data,
            log_data,
            status_code,
            sailthru_secret
    ):
        """
        Verify the endpoint logged a failure message
        when it failed to update the email status in offer_assignment
        """
        with override_settings(SAILTHRU_SECRET=sailthru_secret):
            with LogCapture(level=logging.INFO) as log:
                response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        log.check_present(
            (self.log_name, 'ERROR', log_data),
        )
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, response.json())

    @ddt.data(
        (
            {
                'email': 'blashsdsd@dfsdf.com',
                'send_id': 'WFQKQW5K3LBgi0mk',
                'action': 'hardbounce',
                'api_key': 'abc123',
                'sig': 'e705b3d5964e82c82136cadd68020384',
            },
            {},
            200,
        ),
    )
    @ddt.unpack
    def test_email_status_update_success(
            self,
            post_data,
            response_data,
            status_code
    ):
        """ Verify the endpoint updated the email status in offer_assignment """
        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=None)
        offer_assignment = factories.OfferAssignmentFactory(
            offer=enterprise_offer,
            code='jfhrmndk554lwre',
            user_email='johndoe@unknown.com',
            status=OFFER_ASSIGNED
        )
        OfferAssignmentEmailAttempt.objects.create(offer_assignment=offer_assignment, send_id=post_data.get('send_id'))
        with LogCapture(level=logging.INFO) as log:
            with mock.patch("ecommerce.extensions.api.v2.views.assignmentemail.SailthruClient.receive_hardbounce_post",
                            return_value=True):
                response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        log.check_present()
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, response.json())
        updated_offer_assignment = OfferAssignment.objects.get(id=offer_assignment.id)
        self.assertEqual(updated_offer_assignment.status, OFFER_ASSIGNMENT_EMAIL_BOUNCED)
