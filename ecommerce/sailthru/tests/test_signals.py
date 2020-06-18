"""Tests of ecommerce sailthru signal handlers."""


import logging

from mock import patch
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory

from ecommerce.core.tests import toggle_switch
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.test.factories import create_order
from ecommerce.sailthru.signals import SAILTHRU_CAMPAIGN, process_basket_addition, process_checkout_complete
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

BasketAttributeType = get_model('basket', 'BasketAttributeType')
log = logging.getLogger(__name__)

TEST_EMAIL = 'test@edx.org'
CAMPAIGN_COOKIE = 'cookie_bid'


class SailthruSignalTests(CouponMixin, DiscoveryTestMixin, TestCase):
    """ Tests for the Sailthru signals. """

    def setUp(self):
        super(SailthruSignalTests, self).setUp()
        self.request.COOKIES['sailthru_bid'] = CAMPAIGN_COOKIE
        self.user = UserFactory.create(username='test', email=TEST_EMAIL)

        toggle_switch('sailthru_enable', True)
        self.site_configuration.enable_sailthru = True
        self.site_configuration.save()

        # create some test course objects
        self.course_id = 'edX/toy/2012_Fall'
        self.course_url = 'http://lms.testserver.fake/courses/edX/toy/2012_Fall/info'
        self.course = CourseFactory(id=self.course_id, name='Demo Course', partner=self.partner)

        self.basket_attribute_type, __ = BasketAttributeType.objects.get_or_create(name=SAILTHRU_CAMPAIGN)

    @patch('ecommerce.sailthru.signals.logger.error')
    def test_signals_disabled(self, mock_log_error):
        """ Verify Sailthru is not contacted if the signals are disabled. """
        toggle_switch('sailthru_enable', False)
        process_checkout_complete(None)
        self.assertFalse(mock_log_error.called)

        process_basket_addition(None)
        self.assertFalse(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    @patch('ecommerce.sailthru.signals.logger.error')
    def test_partner_not_supported(self, mock_log_error, mock_update_course_enrollment):
        """ Verify Sailthru is not contacted if the feature is disabled for the site. """
        self.site_configuration.enable_sailthru = False
        self.site_configuration.save()

        process_basket_addition(None, request=self.request)
        self.assertFalse(mock_update_course_enrollment.called)
        self.assertFalse(mock_log_error.called)

        __, order = self._create_order(99)
        process_checkout_complete(None, order=order)
        self.assertFalse(mock_update_course_enrollment.called)
        self.assertFalse(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    @patch('ecommerce.sailthru.signals.logger.error')
    def test_unsupported_product_class(self, mock_log_error, mock_update_course_enrollment):
        """ Verify Sailthru is not contacted for non-seat products. """
        coupon = self.create_coupon()
        basket = BasketFactory(owner=self.user, site=self.site)
        basket.add_product(coupon, 1)
        process_basket_addition(None, request=self.request, user=self.user, product=coupon, basket=basket)
        self.assertFalse(mock_update_course_enrollment.called)
        self.assertFalse(mock_log_error.called)

        order = create_order(number=1, basket=basket, user=self.user)
        process_checkout_complete(None, order=order, request=None)
        self.assertFalse(mock_update_course_enrollment.called)
        self.assertFalse(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    @patch('ecommerce.sailthru.signals.logger.error')
    def test_stop_sailthru_update_on_multi_product_baskets(self, mock_log_error, mock_update_course_enrollment):
        """ Verify Sailthru is not contacted for multi-product baskets. """
        # Create multi-product basket
        seat = self.course.create_or_update_seat('verified', False, 100, None)
        other_course = CourseFactory(partner=self.partner)
        other_seat = other_course.create_or_update_seat('verified', False, 100, None)
        basket = BasketFactory(owner=self.user, site=self.site)
        basket.add_product(seat)
        basket.add_product(other_seat)
        multi_product_order = create_order(number=2, basket=basket, user=self.user, site=self.site)

        # This method takes an argument to determine whether that product is part of a multi-product basket
        process_basket_addition(None, request=self.request, user=self.user, product=seat, is_multi_product_basket=True)
        self.assertFalse(mock_update_course_enrollment.called)
        self.assertFalse(mock_log_error.called)

        # This method looks at the number of lines in the order to determine if the basket has multiple products
        process_checkout_complete(None, order=multi_product_order, request=None)
        self.assertFalse(mock_update_course_enrollment.called)
        self.assertFalse(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_process_checkout_complete(self, mock_update_course_enrollment):
        """ Verify the post_checkout receiver is called, and contacts Sailthru. """

        seat, order = self._create_order(99)
        process_checkout_complete(None, order=order, request=self.request)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(
            TEST_EMAIL,
            self.course_url,
            False,
            seat.attr.certificate_type,
            course_id=self.course_id,
            currency=order.currency,
            message_id=CAMPAIGN_COOKIE,
            site_code=self.partner.short_code,
            unit_cost=order.total_excl_tax,
            sku=order.lines.first().partner_sku
        )

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_process_checkout_complete_without_request(self, mock_update_course_enrollment):
        """ Verify the post_checkout receiver can handle cases in which it is called without a request. """

        seat, order = self._create_order(99)
        process_checkout_complete(None, order=order)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(
            TEST_EMAIL,
            self.course_url,
            False,
            seat.attr.certificate_type,
            course_id=self.course_id,
            currency=order.currency,
            message_id=None,
            site_code=self.partner.short_code,
            unit_cost=order.total_excl_tax,
            sku=order.lines.first().partner_sku
        )

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_basket_addition(self, mock_update_course_enrollment):
        """ Verify the basket_addition receiver is called, and contacts Sailthru. """

        seat, order = self._create_order(99)
        process_basket_addition(None, request=self.request, user=self.user, product=seat)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(
            TEST_EMAIL,
            self.course_url,
            True,
            seat.attr.certificate_type,
            course_id=self.course_id,
            currency=order.currency,
            message_id=CAMPAIGN_COOKIE,
            site_code=self.partner.short_code,
            unit_cost=order.total_excl_tax
        )

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_basket_addition_with_free_product(self, mock_update_course_enrollment):
        """ Verify Sailthru is not contacted when free items are added to the basket. """

        seat = self._create_order(0)[0]
        process_basket_addition(None, request=self.request, user=self.user, product=seat)
        self.assertFalse(mock_update_course_enrollment.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_basket_attribute_update(self, mock_update_course_enrollment):
        """ Verify the Sailthru campaign ID is saved as a basket attribute. """

        seat, order = self._create_order(99)
        process_basket_addition(None, request=self.request, user=self.user, product=seat, basket=order.basket)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(
            TEST_EMAIL,
            self.course_url,
            True,
            seat.attr.certificate_type,
            course_id=self.course_id,
            currency=order.currency,
            message_id=CAMPAIGN_COOKIE,
            site_code=self.partner.short_code,
            unit_cost=order.total_excl_tax
        )

        # now call checkout_complete with the same basket to see if campaign id saved and restored
        process_checkout_complete(None, order=order, request=None)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(
            TEST_EMAIL,
            self.course_url,
            False,
            seat.attr.certificate_type,
            course_id=self.course_id,
            currency=order.currency,
            message_id=CAMPAIGN_COOKIE,
            site_code=self.partner.short_code,
            unit_cost=order.total_excl_tax,
            sku=order.lines.first().partner_sku
        )

    def test_basket_attribute_update_with_existing_attribute(self):
        """ Verify existing BasketAttribute values are updated if a user is modifying an existing basket. """
        campaign_id = 'attempt-1'
        seat, order = self._create_order(99)
        basket = order.basket
        self.request.COOKIES['sailthru_bid'] = campaign_id
        process_basket_addition(None, request=self.request, user=self.user, product=seat, basket=basket)
        self.assertEqual(basket.basketattribute_set.get(attribute_type=self.basket_attribute_type).value_text,
                         campaign_id)

        # Call again to trigger another attempt to create an attribute
        campaign_id = 'attempt-2'
        self.request.COOKIES['sailthru_bid'] = campaign_id
        process_basket_addition(None, request=self.request, user=self.user, product=seat, basket=basket)
        self.assertEqual(basket.basketattribute_set.get(attribute_type=self.basket_attribute_type).value_text,
                         campaign_id)

    @patch('ecommerce_worker.sailthru.v1.tasks.update_course_enrollment.delay')
    def test_save_campaign_id_for_audit_enrollments(self, mock_update_course_enrollment):
        """ Verify the Sailthru campaign ID is saved as a basket attribute for audit enrollments. """

        seat, order = self._create_order(0, 'audit')
        process_basket_addition(None, request=self.request, user=self.user, product=seat, basket=order.basket)
        self.assertFalse(mock_update_course_enrollment.called)

        # now call checkout_complete with the same basket to see if campaign id saved and restored
        process_checkout_complete(None, order=order, request=None)
        self.assertTrue(mock_update_course_enrollment.called)
        mock_update_course_enrollment.assert_called_with(
            TEST_EMAIL,
            self.course_url,
            False,
            seat.attr.certificate_type,
            course_id=self.course_id,
            currency=order.currency,
            message_id=CAMPAIGN_COOKIE,
            site_code=self.partner.short_code,
            unit_cost=order.total_excl_tax,
            sku=order.lines.first().partner_sku
        )

    def _create_order(self, price, mode='verified'):
        seat = self.course.create_or_update_seat(mode, False, price, None)

        basket = BasketFactory(owner=self.user, site=self.site)
        basket.add_product(seat, 1)
        order = create_order(number=1, basket=basket, user=self.user, site=self.site)
        order.total_excl_tax = price
        return seat, order
