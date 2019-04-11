import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from oscar.core.loading import get_model

from ecommerce.enterprise.utils import get_enterprise_customer
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')


def send_new_codes_notification_email(site, email_address, enterprise_id, coupon_id):
    """
    Send new codes email notification to an enterprise customer.

    Arguments:
        site (str): enterprise customer site
        email_address (str): recipient email address of the enterprise customer
        enterprise_id (str): enterprise customer uuid
        coupon_id (str): id of the newly created coupon
    """
    enterprise_customer_object = get_enterprise_customer(site, enterprise_id)
    enterprise_slug = enterprise_customer_object.get('slug')

    try:
        send_mail(
            subject=settings.NEW_CODES_EMAIL_CONFIG['email_subject'],
            message=settings.NEW_CODES_EMAIL_CONFIG['email_body'].format(enterprise_slug=enterprise_slug),
            from_email=settings.NEW_CODES_EMAIL_CONFIG['from_email'],
            recipient_list=[email_address],
            fail_silently=False
        )
    except SMTPException:
        logger.exception(
            'New codes email failed for enterprise customer [%s] for coupon [%s]',
            enterprise_id,
            coupon_id
        )

    logger.info('New codes email sent to enterprise customer [%s] for coupon [%s]', enterprise_id, coupon_id)


def get_enterprise_from_product(product_id):
    """
    Retrieve enterprise_id from a given Product (coupon)

    :param product_id (str): Coupon product id
    :return: enterprise_id (str): enterprise customer uuid or None
    """
    try:
        product = Product.objects.get(pk=product_id)
        basket = Basket.objects.filter(lines__product_id=product.id).first()
        invoice = Invoice.objects.get(order__basket=basket)
        return str(invoice.business_client.enterprise_customer_uuid)
    except (Product.DoesNotExist, Invoice.DoesNotExist):
        return None
