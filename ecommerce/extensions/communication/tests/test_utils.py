import mock
from django.conf import settings

from ecommerce.extensions.communication.utils import Dispatcher
from ecommerce.tests.testcases import TestCase


class TestDispatcher(TestCase):

    def setUp(self):
        super(TestDispatcher, self).setUp()
        self.user = self.create_user(is_staff=False, email="user@example.com")

    @mock.patch('ecommerce.extensions.communication.utils.EmailMessage')
    def test_send_email_messages_no_html(self, mock_email_message):
        dispatcher = Dispatcher()
        messages = {
            'subject': 'Test Subject',
            'body': 'Test Body',
        }
        dispatcher.send_email_messages('recipient@example.com', messages)
        mock_email_message.assert_called_once_with(
            'Test Subject',
            'Test Body',
            from_email=settings.OSCAR_FROM_EMAIL,
            to=['recipient@example.com']
        )

    @mock.patch('ecommerce.extensions.communication.utils.EmailMessage')
    def test_send_email_messages_plain(self, mock_email_message):
        dispatcher = Dispatcher()
        messages = {
            'subject': 'Test Subject',
            'body': 'Test Body',
            'html': None
        }
        dispatcher.send_email_messages('recipient@example.com', messages)
        mock_email_message.assert_called_once_with(
            'Test Subject',
            'Test Body',
            from_email=settings.OSCAR_FROM_EMAIL,
            to=['recipient@example.com']
        )

    @mock.patch('ecommerce.extensions.communication.utils.EmailMultiAlternatives')
    def test_send_email_messages_html(self, mock_email_multi_alternatives):
        dispatcher = Dispatcher()
        mock_email_instance = mock_email_multi_alternatives.return_value

        messages = {
            'subject': 'Test Subject',
            'body': 'Test Body',
            'html': '<html><body>Test HTML Body</body></html>'
        }
        dispatcher.send_email_messages('recipient@example.com', messages)
        mock_email_multi_alternatives.assert_called_once_with(
            'Test Subject',
            'Test Body',
            from_email=settings.OSCAR_FROM_EMAIL,
            to=['recipient@example.com']
        )
        mock_email_instance.attach_alternative.assert_called_once_with(
            '<html><body>Test HTML Body</body></html>',
            "text/html"
        )
