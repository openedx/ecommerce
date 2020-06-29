

import datetime

import ddt
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from oscar.core.loading import get_model
from oscar.test.factories import OrderFactory, OrderLineFactory

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_REVOKED, OFFER_REDEEMED
from ecommerce.extensions.test import factories
from ecommerce.tests.factories import PartnerFactory, UserFactory
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
class VoucherTests(TestCase):
    def setUp(self):
        super(VoucherTests, self).setUp()
        self.data = {
            'code': 'TESTCODE',
            'end_datetime': now() + datetime.timedelta(days=1),
            'start_datetime': now() - datetime.timedelta(days=1)
        }

    def test_create_voucher(self):
        """ Verify voucher is created. """
        voucher = Voucher.objects.create(**self.data)
        self.assertEqual(voucher.code, self.data['code'])
        self.assertEqual(voucher.start_datetime, self.data['start_datetime'])
        self.assertEqual(voucher.end_datetime, self.data['end_datetime'])

    def test_no_code_raises_exception(self):
        """ Verify creating voucher without code set raises exception. """
        del self.data['code']
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    def test_wrong_code_data_raises_exception(self):
        """ Verify creating voucher with code value that contains spaces (non alphanumeric value) raises exception. """
        self.data['code'] = 'Only alphanumeric without spaces'
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    @ddt.data('end_datetime', 'start_datetime')
    def test_no_datetime_set_raises_exception(self, key):
        """ Verify creating voucher without start/end datetime set raises exception. """
        del self.data[key]
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    @ddt.data('end_datetime', 'start_datetime')
    def test_incorrect_datetime_value_raises_exception(self, key):
        """ Verify creating voucher with incorrect start/end datetime value raises exception. """
        self.data[key] = 'incorrect value'
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    def test_start_datetime_after_end_datetime(self):
        """ Verify creating voucher with start datetime set after end datetime raises exception. """
        self.data['start_datetime'] = self.data['end_datetime'] + datetime.timedelta(days=1)
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    def test_best_offer(self):
        voucher = Voucher.objects.create(**self.data)
        first_offer = factories.ConditionalOfferFactory()
        voucher.offers.add(first_offer)
        assert voucher.best_offer == first_offer
        # Now add a second enterprise offer, and see that the enterprise offer gets returned.
        second_offer = factories.EnterpriseOfferFactory()
        voucher.offers.add(second_offer)
        assert voucher.best_offer == second_offer
        # Add a third enterprise offer, and see that the first enterprise offer gets returned
        # because of multiple enterprise offers being available.
        third_offer = factories.EnterpriseOfferFactory()
        voucher.offers.add(third_offer)
        assert voucher.best_offer == second_offer

    def test_create_voucher_with_multi_use_per_customer_usage(self):
        """ Verify voucher is created with `MULTI_USE_PER_CUSTOMER` usage type. """
        voucher_data = dict(self.data, usage=Voucher.MULTI_USE_PER_CUSTOMER)
        voucher = Voucher.objects.create(**voucher_data)
        user = UserFactory()
        self.assertEqual(voucher.usage, Voucher.MULTI_USE_PER_CUSTOMER)
        is_available, message = voucher.is_available_to_user(user)
        self.assertTrue(is_available)
        self.assertEqual(message, '')

    def use_voucher(self, voucher, user):
        """
        Mark voucher as used by provided user
        """
        partner = PartnerFactory(short_code='testX')
        course = CourseFactory(id='course-v1:test-org+course+run', partner=partner)
        verified_seat = course.create_or_update_seat('verified', False, 100)

        order = OrderFactory()
        order_line = OrderLineFactory(product=verified_seat, partner_sku='test_sku')
        order.lines.add(order_line)
        voucher.record_usage(order, user)
        voucher.offers.first().record_usage(discount={'freq': 1, 'discount': 1})

    def test_multi_use_per_customer_voucher(self):
        """
        Verify `MULTI_USE_PER_CUSTOMER` behaves as expected.
        """
        voucher_data = dict(self.data, usage=Voucher.MULTI_USE_PER_CUSTOMER)
        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=3)
        voucher = factories.VoucherFactory(**voucher_data)
        voucher.offers.add(enterprise_offer)

        user1 = UserFactory(email='test1@example.com')
        user2 = UserFactory(email='test2@example.com')

        self.use_voucher(voucher, user1)

        is_available, message = voucher.is_available_to_user(user1)
        assert (is_available, message) == (True, '')

        is_available, message = voucher.is_available_to_user(user2)
        assert (is_available, message) == (False, 'This voucher is assigned to another user.')

    def test_slots_available_for_assignment_no_enterprise_offer(self):
        """ Verify that a voucher with no enterprise offer returns none for slots_available_for_assignment. """
        voucher = Voucher.objects.create(**self.data)
        assert not voucher.slots_available_for_assignment

    def test_not_redeemed_assignment_ids_with_non_enterprise_offer(self):
        """ Verify that a voucher with no enterprise offer returns none for not_redeemed_assignment_ids. """
        voucher = Voucher.objects.create(**self.data)
        assert not voucher.not_redeemed_assignment_ids

    @ddt.data(
        (Voucher.SINGLE_USE, 0, None, [], 1),
        (Voucher.MULTI_USE_PER_CUSTOMER, 0, 10, [], 10),
        (Voucher.MULTI_USE, 0, 10, [], 10),
        (Voucher.ONCE_PER_CUSTOMER, 0, 10, [], 10),
        (Voucher.SINGLE_USE, 1, None, [], 0),
        (Voucher.MULTI_USE_PER_CUSTOMER, 3, 10, [], 0),
        (Voucher.MULTI_USE, 3, 10, [], 7),
        (Voucher.SINGLE_USE, 0, None, [{'status': OFFER_ASSIGNED}], 0),
        (Voucher.MULTI_USE_PER_CUSTOMER, 0, 10, [{'status': OFFER_ASSIGNED}, {'status': OFFER_ASSIGNED}], 0),
        (Voucher.MULTI_USE, 0, 10, [{'status': OFFER_ASSIGNED}, {'status': OFFER_ASSIGNED}], 8),
        (Voucher.MULTI_USE, 99, None, [{'status': OFFER_ASSIGNED}], 9900),
        (Voucher.MULTI_USE, 3, 10, [{'status': OFFER_REDEEMED}], 7),
        (Voucher.SINGLE_USE, 0, None, [{'status': OFFER_ASSIGNMENT_REVOKED}], 1),
        (Voucher.MULTI_USE_PER_CUSTOMER, 0, 10, [{'status': OFFER_ASSIGNMENT_REVOKED}], 10),
        (Voucher.MULTI_USE_PER_CUSTOMER, 1, 10, [{'status': OFFER_ASSIGNMENT_REVOKED}], 0),
    )
    @ddt.unpack
    def test_slots_available_for_assignment(self, usage, num_orders, max_uses, offer_assignments, expected):
        voucher_data = dict(self.data, usage=usage, num_orders=num_orders)
        voucher = Voucher.objects.create(**voucher_data)

        enterprise_offer = factories.EnterpriseOfferFactory(max_global_applications=max_uses)
        voucher.offers.add(enterprise_offer)

        for assignment_data in offer_assignments:
            factories.OfferAssignmentFactory(offer=enterprise_offer, code=voucher.code, **assignment_data)

        assert voucher.slots_available_for_assignment == expected
