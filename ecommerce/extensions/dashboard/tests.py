from django.core.urlresolvers import reverse
from django.test import TestCase
from oscar.core.loading import get_model
from ecommerce.extensions.test.factories import UserFactory, OrderFactory


Partner = get_model('partner', 'Partner')


class DashboardViewTestMixin(object):
    def assert_message_equals(self, response, msg, level):  # pylint: disable=unused-argument
        """ Verify the latest message matches the expected value. """
        messages = []
        for context in response.context:
            messages += context.get('messages', [])

        message = messages[0]
        self.assertEqual(message.level, level)
        self.assertEqual(message.message, msg)


class ExtendedIndexViewTests(TestCase):
    def test_average_paid_order_costs(self):
        """ Verify the stats contain average_paid_order_costs. """
        partner, __ = Partner.objects.get_or_create(short_code='edx', name='edx')

        password = 'password'
        user = UserFactory(is_staff=True, password=password)
        self.client.login(username=user.username, password=password)
        response = self.client.get(reverse('dashboard:index'))

        actual = response.context['average_paid_order_costs']
        self.assertEqual(actual, 0)

        order = OrderFactory(basket__partner=partner)
        actual = response.context['average_paid_order_costs']
        self.assertEqual(actual, order.total_incl_tax)
