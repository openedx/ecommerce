

import json
import logging

import ddt
from django.urls import reverse
from testfixtures import LogCapture

from ecommerce.extensions.offer.constants import OFFER_ASSIGNED
from ecommerce.extensions.offer.models import OfferAssignment
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
