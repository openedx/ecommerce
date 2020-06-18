

from django.urls import reverse
from oscar.test.factories import OrderFactory

from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase


class DashboardViewTestMixin:
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
        password = 'password'
        user = UserFactory(is_staff=True, password=password)
        self.client.login(username=user.username, password=password)
        response = self.client.get(reverse('dashboard:index'))

        actual = response.context['average_paid_order_costs']
        self.assertEqual(actual, 0)

        order = OrderFactory()
        actual = response.context['average_paid_order_costs']
        self.assertEqual(actual, order.total_incl_tax)
