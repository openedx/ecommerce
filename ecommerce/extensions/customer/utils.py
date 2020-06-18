

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from oscar.apps.customer.utils import *  # pylint: disable=wildcard-import, unused-wildcard-import


# pylint: disable=abstract-method, function-redefined
class Dispatcher(Dispatcher):

    def dispatch_direct_messages(self, recipient, messages, site=None):  # pylint: disable=arguments-differ
        """
        Dispatch one-off messages to explicitly specified recipient(s).
        """
        if messages['subject'] and messages['body']:
            self.send_email_messages(recipient, messages, site)

    def dispatch_order_messages(self, order, messages, event_type=None, site=None, **kwargs):  # pylint: disable=arguments-differ
        """
        Dispatch order-related messages to the customer
        """
        # Note: We do not support anonymous orders
        self.dispatch_user_messages(order.user, messages, site)

        # Create order communications event for audit
        if event_type is not None:
            # pylint: disable=protected-access
            CommunicationEvent._default_manager.create(order=order, event_type=event_type)

    def dispatch_user_messages(self, user, messages, site=None, recipient=None):  # pylint: disable=arguments-differ
        """
        Send messages to a site user
        """
        if messages['subject'] and (messages['body'] or messages['html']):
            self.send_user_email_messages(user, messages, site, recipient)
        if messages['sms']:
            self.send_text_message(user, messages['sms'])

    def send_user_email_messages(self, user, messages, site=None, recipient=None):  # pylint: disable=arguments-differ
        """
        Sends message to the registered user / customer and collects data in
        database
        """
        if not (recipient or user.email):
            msg = "Unable to send email messages: No email address for '{username}'.".format(username=user.username)
            self.logger.warning(msg)
            return

        recipient = recipient if recipient else user.email
        email = self.send_email_messages(recipient, messages, site)

        # Is user is signed in, record the event for audit
        if email and user.is_authenticated:
            # pylint: disable=protected-access
            Email._default_manager.create(user=user,
                                          subject=email.subject,
                                          body_text=email.body,
                                          body_html=messages['html'])

    def send_email_messages(self, recipient, messages, site=None):  # pylint:disable=arguments-differ
        """
        Plain email sending to the specified recipient
        """
        from_email = settings.OSCAR_FROM_EMAIL
        if site:
            from_email = site.siteconfiguration.get_from_email()

        # Determine whether we are sending a HTML version too
        if messages['html']:
            email = EmailMultiAlternatives(messages['subject'],
                                           messages['body'],
                                           from_email=from_email,
                                           to=[recipient])
            email.attach_alternative(messages['html'], "text/html")
        else:
            email = EmailMessage(messages['subject'],
                                 messages['body'],
                                 from_email=from_email,
                                 to=[recipient])
        self.logger.info("Sending email to %s", recipient)
        email.send()

        return email
