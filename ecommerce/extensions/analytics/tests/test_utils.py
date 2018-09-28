import json

import ddt
import mock
from django.contrib.auth.models import AnonymousUser
from django.test.client import RequestFactory
from oscar.test import factories

from analytics import Client
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.analytics.utils import (
    ECOM_TRACKING_ID_FMT,
    get_google_analytics_client_id,
    parse_tracking_context,
    prepare_analytics_data,
    track_segment_event,
    translate_basket_line_for_segment
)
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.testcases import TransactionTestCase


@ddt.ddt
class UtilsTest(DiscoveryTestMixin, BasketMixin, TransactionTestCase):
    """ Tests for the analytics utils. """

    def test_prepare_analytics_data(self):
        """ Verify the function returns correct analytics data for a logged in user."""
        user = self.create_user(
            first_name='John',
            last_name='Doe',
            email='test@example.com',
            tracking_context={'lms_user_id': '1235123'}
        )
        data = prepare_analytics_data(user, self.site.siteconfiguration.segment_key)
        self.assertDictEqual(json.loads(data), {
            'tracking': {'segmentApplicationId': self.site.siteconfiguration.segment_key},
            'user': {'user_tracking_id': '1235123', 'name': 'John Doe', 'email': 'test@example.com'}
        })

    def test_anon_prepare_analytics_data(self):
        """ Verify the function returns correct analytics data for an anonymous user."""
        user = AnonymousUser()
        data = prepare_analytics_data(user, self.site.siteconfiguration.segment_key)
        self.assertDictEqual(json.loads(data), {
            'tracking': {'segmentApplicationId': self.site.siteconfiguration.segment_key},
            'user': 'AnonymousUser'
        })

    def test_parse_tracking_context(self):
        """ The method should parse the tracking context on the User object. """
        tracking_context = {
            'ga_client_id': 'test-client-id',
            'lms_user_id': 'foo',
            'lms_ip': '18.0.0.1',
        }
        user = self.create_user(tracking_context=tracking_context)
        expected = (tracking_context['lms_user_id'], tracking_context['ga_client_id'], tracking_context['lms_ip'])
        self.assertEqual(parse_tracking_context(user), expected)

        # If no LMS user ID is provided, we should create one based on the E-Commerce ID
        del tracking_context['lms_user_id']
        user = self.create_user(tracking_context=tracking_context)
        expected = (ECOM_TRACKING_ID_FMT.format(user.id), tracking_context['ga_client_id'], tracking_context['lms_ip'])
        self.assertEqual(parse_tracking_context(user), expected)

    def test_track_segment_event_without_segment_key(self):
        """ If the site has no Segment key, the function should log a debug message and NOT send an event."""
        self.site_configuration.segment_key = None
        self.site_configuration.save()

        with mock.patch('logging.Logger.debug') as mock_debug:
            msg = 'Event [foo] was NOT fired because no Segment key is set for site configuration [{}]'
            msg = msg.format(self.site_configuration.pk)
            self.assertEqual(track_segment_event(self.site, self.create_user(), 'foo', {}), (False, msg))
            mock_debug.assert_called_with(msg)

    def test_track_segment_event(self):
        """ The function should fire an event to Segment if the site is properly configured. """
        self.site_configuration.segment_key = 'fake-key'
        self.site_configuration.save()
        user, event, properties = self._get_generic_segment_event_parameters()
        user_tracking_id, ga_client_id, lms_ip = parse_tracking_context(user)
        context = {
            'ip': lms_ip,
            'Google Analytics': {
                'clientId': ga_client_id
            }
        }
        with mock.patch.object(Client, 'track') as mock_track:
            track_segment_event(self.site, user, event, properties)
            mock_track.assert_called_once_with(user_tracking_id, event, properties, context=context)

    def test_translate_basket_line_for_segment(self):
        """ The method should return a dict formatted for Segment. """
        basket = create_basket(empty=True)
        basket.site = self.site
        basket.owner = factories.UserFactory()
        basket.save()
        course = CourseFactory(partner=self.partner)
        seat = course.create_or_update_seat('verified', True, 100)
        basket.add_product(seat)
        line = basket.lines.first()
        expected = {
            'product_id': seat.stockrecords.first().partner_sku,
            'sku': 'verified',
            'name': course.id,
            'price': '100.00',
            'quantity': 1,
            'category': 'Seat',
        }
        self.assertEqual(translate_basket_line_for_segment(line), expected)

        # Products not associated with a Course should still be reported with the product's title instead of
        # the course ID.
        seat.course = None
        seat.save()

        # Refresh the basket
        basket.flush()
        basket.add_product(seat)
        line = basket.lines.first()

        expected['name'] = seat.title
        self.assertEqual(translate_basket_line_for_segment(line), expected)

        seat.course = None
        seat.save()
        course.delete()
        expected['name'] = seat.title
        self.assertEqual(translate_basket_line_for_segment(line), expected)

    def test_get_google_analytics_client_id(self):
        """ Test that method return's the GA clientId. """
        expected_client_id = get_google_analytics_client_id(None)
        self.assertIsNone(expected_client_id)

        ga_client_id = 'test-client-id'
        request_factory = RequestFactory()
        request_factory.cookies['_ga'] = 'GA1.2.{}'.format(ga_client_id)
        request = request_factory.get('/')

        expected_client_id = get_google_analytics_client_id(request)
        self.assertEqual(ga_client_id, expected_client_id)

    def _get_generic_segment_event_parameters(self):
        properties = {'key': 'value'}
        user = self.create_user(
            tracking_context={
                'ga_client_id': 'test-client-id',
                'lms_user_id': 'foo',
                'lms_ip': '18.0.0.1',
            })
        event = 'foo'
        return user, event, properties
