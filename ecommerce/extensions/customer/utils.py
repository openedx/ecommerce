from oscar.apps.customer.utils import Dispatcher as OscarDispatcher


class Dispatcher(OscarDispatcher):

    def send_email_messages(self, recipient, messages):
        """
        Plain email sending to the specified recipient
        """
        if hasattr(settings, 'OSCAR_FROM_EMAIL'):
            from_email = settings.OSCAR_FROM_EMAIL
        else:
            from_email = None

        # Determine whether we are sending a HTML version too
        if messages['html']:
            email = EmailMultiAlternatives(messages['subject'],
                                           messages['body'],
                                           from_email=from_email,
                                           to=[recipient],
                                           attachments=messages.get('attachments'))
            email.attach_alternative(messages['html'], "text/html")
        else:
            email = EmailMessage(messages['subject'],  # pylint: disable=redefined-variable-type
                                 messages['body'],
                                 from_email=from_email,
                                 to=[recipient],
                                 attachments=messages.get('attachments'))
        self.logger.info("Sending email to %s" % recipient)
        email.send()

        return email

    def send_text_message(self, user, event_type):
        raise NotImplementedError

from oscar.apps.customer.utils import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,ungrouped-imports
