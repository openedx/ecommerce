from __future__ import unicode_literals

import json
import logging

import ddt
from django.urls import reverse
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_BOUNCED
from ecommerce.extensions.offer.models import OfferAssignment, OfferAssignmentEmailAttempt
from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class AssignmentEmailTests(TestCase):
    """ Tests for AssignmentEmail API view. """
    path = reverse('api:v2:assignmentemail:get_template')

    def setUp(self):
        super(AssignmentEmailTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def test_authentication_required(self):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)

    def test_successful_get(self):
        """ Verify that get returns the default template """
        expected_data = ('Your learning manager has provided you with a new access code to take a course at edX.'
                         ' You may redeem this code for {code_usage_count} courses. '

                         'edX login: {user_email}'
                         'Enrollment url: {enrollment_url}'
                         'Access Code: {code}'
                         'Expiration date: {code_expiration_date}'

                         'You may go directly to the Enrollment URL to view courses that are available for this code'
                         ' or you can insert the access code at check out under "coupon code" for applicable courses.'

                         'For any questions, please reach out to your Learning Manager.')
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(response.data, {'template': expected_data})


@ddt.ddt
class AssignmentEmailStatusTests(TestCase):
    """ Tests for AssignmentEmailStatus API view. """
    path = reverse('api:v2:assignmentemail:update_status')

    def setUp(self):
        super(AssignmentEmailStatusTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.data = {
            'offer_id': 556,
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
                'offer_id': 555,
                'send_id': 'XBEn85WnoQJsIhk6',
                'status': 'success',
            },
            {
                'offer_id': 555,
                'send_id': 'XBEn85WnoQJsIhk6',
                'status': 'failed',
                'error': 'OfferAssignment matching query does not exist.'
            },
            200,
        ),
    )
    @ddt.unpack
    def test_email_status_update_failure(
            self,
            post_data,
            response_data,
            status_code,
    ):
        """
        Verify the endpoint returned the failed status when
        requisite are keys not present in offer_assignment model
        """
        log_name = 'ecommerce.extensions.api.v2.views.assignmentemail'
        with LogCapture(level=logging.INFO) as log:
            response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        log.check(
            (log_name, 'ERROR',
             "[Offer Assignment] AssignmentEmailStatus update raised: "
             "DoesNotExist('OfferAssignment matching query does not exist.',)"),
        )
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, json.loads(response.content))

    @ddt.data(
        (
            # A valid request.
            {
                'offer_id': 1,
                'send_id': 'XBEn85WnoQJsIhk7',
                'status': 'success',
            },
            {
                'offer_id': 1,
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
        post_data['offer_id'] = offer_assignment.id
        response_data['offer_id'] = offer_assignment.id
        response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, json.loads(response.content))
        updated_offer_assignment = OfferAssignment.objects.get(id=offer_assignment.id)
        self.assertEqual(updated_offer_assignment.status, OFFER_ASSIGNED)


@ddt.ddt
class AssignmentEmailBounceTests(TestCase):
    """ Tests for AssignmentEmailBounce API view. """
    path = reverse('api:v2:assignmentemail:receive_bounce')

    def setUp(self):
        super(AssignmentEmailBounceTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    @ddt.data(
        (
            # Exception while accessing model.
            {
                'email': 'blashsdsd@dfsdf.com',
                'send_id': 'WFQKQW5K3LBgi0mk',
                'action': 'hardbounce',
                'api_key': '6b805755ce5a23e3c0459aaa598efc56',
                'sig': '13b3987b656c7771fcac92982fdfb331',
            },
            {},
            200,
        ),
    )
    @ddt.unpack
    def test_email_status_update_failure(
            self,
            post_data,
            response_data,
            status_code,
    ):
        """
        Verify the endpoint logged a failure message
        when it failed to update the email status in offer_assignment
        """
        log_name = 'ecommerce.extensions.api.v2.views.assignmentemail'
        with LogCapture(level=logging.INFO) as log:
            response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        log.check(
            (log_name, 'ERROR',
             "[Offer Assignment] AssignmentEmailBounce could not update status and raised: DoesNotExist("
             "'OfferAssignmentEmailAttempt matching query does not exist.',)"),
        )
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, json.loads(response.content))

    @ddt.data(
        (
            # Exception while accessing model.
            {
                'email': 'blashsdsd@dfsdf.com',
                'send_id': 'WFQKQW5K3LBgi0mk',
                'action': 'hardbounce',
                'api_key': '6b805755ce5a23e3c0459aaa598efc56',
                'sig': '13b3987b656c7771fcac92982fdfb331',
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
            status_code,
    ):
        """ Verify the endpoint updated the email status in offer_assignment """
        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=None)
        offer_assignment = factories.OfferAssignmentFactory(
            offer=enterprise_offer,
            code='jfhrmndk554lwre',
            user_email='johndoe@unknown.com',
        )
        OfferAssignmentEmailAttempt.objects.create(offer_assignment=offer_assignment, send_id=post_data.get('send_id'))
        with LogCapture(level=logging.INFO) as log:
            response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        log.check()
        self.assertEqual(response.status_code, status_code)
        self.assertDictEqual(response_data, json.loads(response.content))
        updated_offer_assignment = OfferAssignment.objects.get(id=offer_assignment.id)
        self.assertEqual(updated_offer_assignment.status, OFFER_ASSIGNMENT_EMAIL_BOUNCED)
