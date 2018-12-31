import logging

from smtplib import SMTPException
from django.core.mail import send_mail
from django.core.validators import ValidationError, validate_email
from ecommerce.enterprise.utils import get_enterprise_customer

logger = logging.getLogger(__name__)


def send_new_codes_notification_email(site, email_address, enterprise_id):
    """
    Send new codes email notification
    """
    email_subject = 'New edX codes available'
    from_email = 'customersuccess@edx.org'
    enterprise_customer_object = get_enterprise_customer(site, enterprise_id) if site else {}
    enterprise_slug = enterprise_customer_object.get('slug', '')
    message = '''
        Hello,

        This message is to inform you that a new order has been processed for your organization. Please visit the following page, in your Admin Dashboard, to find new codes ready for use.

        https://portal.edx.org/{token_enterprise_slug}/admin/codes

        Having trouble accessing your codes? Please contact edX Enterprise Support at customersuccess@edx.org.
        Thank you.
    '''.format(token_enterprise_slug=enterprise_slug)

    try:
        if not enterprise_slug:
            raise ValidationError
        validate_email(email_address)
        send_mail(
            subject=email_subject,
            message=message,
            from_email=from_email,
            recipient_list=[email_address],
            fail_silently=False
        )
    except (ValidationError, SMTPException):
        logger.error('Error sending new codes availability notification email for %s', email_address)
