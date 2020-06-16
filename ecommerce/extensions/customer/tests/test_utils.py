

from django.conf import settings
from django.core import mail
from django.test import RequestFactory
from oscar.core.loading import get_model

from ecommerce.extensions.customer.utils import Dispatcher
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

CommunicationEventType = get_model('customer', 'CommunicationEventType')


class CustomerUtilsTests(TestCase):

    def setUp(self):
        super(CustomerUtilsTests, self).setUp()
        self.dispatcher = Dispatcher()
        self.request = RequestFactory()
        self.user = self.create_user()
        self.user.email = 'test_user@example.com'
        self.request.user = self.user
        self.site_configuration = SiteConfigurationFactory(partner__name='Tester', from_email='from@example.com')
        self.request.site = self.site_configuration.site
        self.order = create_order()
        self.order.user = self.user

    def test_dispatch_direct_messages(self):
        recipient = 'test_dispatch_direct_messages@example.com'
        messages = {
            'subject': 'The message subject.',
            'body': 'The message body.',
            'html': '<p>The message html body.</p>'
        }
        self.dispatcher.dispatch_direct_messages(recipient, messages, self.request.site)
        self.assertEqual(mail.outbox[0].from_email, self.site_configuration.from_email)
        mail.outbox = []

        # Test graceful failure paths
        messages = {
            'subject': None,
            'body': 'The message body.',
            'html': '<p>The message html body.</p>'
        }
        self.dispatcher.dispatch_direct_messages(recipient, messages, self.request.site)
        self.assertEqual(len(mail.outbox), 0)

        messages = {
            'subject': "The subject",
            'body': None,
            'html': '<p>The message html body.</p>'
        }
        self.dispatcher.dispatch_direct_messages(recipient, messages, self.request.site)
        self.assertEqual(len(mail.outbox), 0)

    def test_dispatch_order_messages(self):
        messages = {
            'subject': 'The message subject.',
            'body': 'The message body.',
            'html': '<p>The message html body.</p>',
            'sms': None  # Text messaging is currently NotImplemented
        }
        event_type = CommunicationEventType.objects.create(
            email_body_template="Body Template",
            email_body_html_template="<p>Body HTML Template</p>"
        )
        self.dispatcher.dispatch_order_messages(self.order, messages, event_type, self.request.site)
        self.assertEqual(mail.outbox[0].from_email, self.site_configuration.from_email)

    def test_dispatch_order_messages_null_eventtype(self):
        messages = {
            'subject': 'The message subject.',
            'body': 'The message body.',
            'html': '<p>The message html body.</p>',
            'sms': None  # Text messaging is currently NotImplemented
        }
        self.dispatcher.dispatch_order_messages(self.order, messages, None, self.request.site)
        self.assertEqual(mail.outbox[0].from_email, self.site_configuration.from_email)

    def test_dispatch_order_messages_sms_notimplemented(self):
        messages = {
            'subject': 'The message subject.',
            'body': 'The message body.',
            'html': '<p>The message html body.</p>',
            'sms': 'This should trigger a NotImplementedException'
        }
        event_type = CommunicationEventType.objects.all().first()
        with self.assertRaises(NotImplementedError):
            self.dispatcher.dispatch_order_messages(self.order, messages, event_type, self.request.site)

    def test_dispatch_order_messages_empty_user_email_workflow(self):
        """
        If the user does not have an email address then the send operation is gracefully exited,
        so there should be no exception raised by this test and coverage should be reflected.
        """
        self.order.user.email = ''
        messages = {
            'subject': 'The message subject.',
            'body': 'The message body.',
            'html': '<p>The message html body.</p>',
            'sms': None
        }
        event_type = CommunicationEventType.objects.all().first()
        self.dispatcher.dispatch_order_messages(self.order, messages, event_type, self.request.site)

    def test_send_email_messages_no_site(self):
        """
        Ensure the send email workflow executes correctly when a site is not specified
        """
        recipient = 'test_dispatch_direct_messages@example.com'
        messages = {
            'subject': 'The message subject.',
            'body': 'The message body.',
            'html': None,
            'sms': None,
        }
        self.dispatcher.send_email_messages(recipient, messages)
        self.assertEqual(mail.outbox[0].from_email, settings.OSCAR_FROM_EMAIL)
