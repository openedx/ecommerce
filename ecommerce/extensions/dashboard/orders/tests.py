from django.contrib.messages import constants as MSG
from django.core.urlresolvers import reverse
from django.test import TestCase
from oscar.core.loading import get_model

from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.mixins import UserMixin


Refund = get_model('refund', 'Refund')


class OrderViewTestsMixin(UserMixin):
    def setUp(self):
        super(OrderViewTestsMixin, self).setUp()

        # Staff permissions are required for this view
        self.user = self.create_user(is_staff=True)

    def assert_successful_response(self, response, orders=None):
        self.assertEqual(response.status_code, 200)

        if orders:
            self.assertListEqual(list(response.context['orders']), orders)


class OrderListViewTests(OrderViewTestsMixin, RefundTestMixin, TestCase):
    path = reverse('dashboard:order-list')
    username = 'hackerman'

    def setUp(self):
        super(OrderListViewTests, self).setUp()

    def test_filtering(self):
        """Verify that the view allows filtering by username."""
        self.create_order(user=self.user)

        new_user = self.create_user(username=self.username)
        new_order = self.create_order(user=new_user)

        self.client.login(username=self.user.username, password=self.password)

        # Username filtering
        response = self.client.get('{path}?username={username}'.format(
            path=self.path,
            username=self.username
        ))
        self.assert_successful_response(response, [new_order])

        # Validate case-insensitive, starts-with username filtering
        response = self.client.get('{path}?username={username}'.format(
            path=self.path,
            # Cut the configured username in half, then invert the fragment's casing.
            username=self.username[:len(self.username) / 2].swapcase()
        ))
        self.assert_successful_response(response, [new_order])


class OrderDetailViewTests(OrderViewTestsMixin, RefundTestMixin, TestCase):
    def setUp(self):
        super(OrderDetailViewTests, self).setUp()

    def assert_message_equals(self, response, msg, level):  # pylint: disable=unused-argument
        """ Verify the latest message matches the expected value. """
        messages = []
        for context in response.context:
            messages += context.get('messages', [])

        message = messages[0]
        self.assertEqual(message.level, level)
        self.assertEqual(message.message, msg)

    def _request_refund(self, order):
        """POST to the view."""

        # Login
        self.client.login(username=self.user.username, password=self.password)

        # POST to the view, creating the Refund
        data = {
            'line_action': 'create_refund',
            'selected_line': order.lines.values_list('id', flat=True)
        }

        for line in order.lines.all():
            data['selected_line_qty_{}'.format(line.id)] = line.quantity

        response = self.client.post(reverse('dashboard:order-detail', kwargs={'number': order.number}), data=data,
                                    follow=True)
        self.assertEqual(response.status_code, 200)

        return response

    def test_create_refund(self):
        """Verify the view creates a Refund for the Order and selected Lines."""
        # Create Order and Lines
        order = self.create_order(user=self.user)
        self.assertFalse(order.refunds.exists())

        # Validate the Refund
        response = self._request_refund(order)
        refund = Refund.objects.latest()
        self.assert_refund_matches_order(refund, order)

        # Verify a message was passed for display
        data = {
            'link_start': '<a href="{}" target="_blank">'.format(
                reverse('dashboard:refunds:detail', kwargs={'pk': refund.pk})),
            'link_end': '</a>',
            'refund_id': refund.pk
        }
        expected = '{link_start}Refund #{refund_id}{link_end} created! ' \
                   'Click {link_start}here{link_end} to view it.'.format(**data)

        self.assert_message_equals(response, expected, MSG.SUCCESS)

    def test_create_refund_error(self):
        """Verify the view does not create a Refund if the selected Lines have already been refunded."""
        refund = self.create_refund()
        order = refund.order

        for line in order.lines.all():
            self.assertTrue(line.refund_lines.exists())

        # No new refunds should be created
        self.assertEqual(Refund.objects.count(), 1)
        response = self._request_refund(order)
        self.assertEqual(Refund.objects.count(), 1)

        # An error message should be displayed.
        self.assert_message_equals(response,
                                   'A refund cannot be created for these lines. They may have already been refunded.',
                                   MSG.ERROR)
