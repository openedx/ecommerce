
import datetime
import io
import logging
from smtplib import SMTPException

import boto3
from django.conf import settings
from django.core.mail import send_mail
from django.utils.text import slugify
from oscar.core.loading import get_model

from ecommerce.enterprise.utils import get_enterprise_customer

logger = logging.getLogger(__name__)

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
        return product.attr.enterprise_customer_uuid
    except Product.DoesNotExist:
        return None


def upload_files_for_enterprise_coupons(files):
    uploaded_files = []
    if files and len(files) > 0:
        try:
            bucket_name = settings.ENTERPRISE_EMAIL_FILE_ATTACHMENTS_BUCKET_NAME
            bucket_location = settings.ENTERPRISE_EMAIL_FILE_ATTACHMENTS_BUCKET_LOCATION
            session = boto3.Session()
            s3 = session.client('s3')

            for file in files:
                file_bytes = bytearray([int(b) for b in file['contents'].split(',')])
                file_buf = io.BytesIO(file_bytes)
                file_buf.seek(0)
                filename = datetime.datetime.now().strftime("%d-%m-%Y at %H.%M.%S") + " " + file['name']
                key = slugify(filename)
                s3.upload_fileobj(file_buf, bucket_name, key,
                                  ExtraArgs={'ContentType': file['type'], 'ACL': 'public-read'})
                url = f"https://{bucket_name}.s3.{bucket_location}.amazonaws.com/{key}"
                uploaded_files.append({'name': key, 'size': file['size'], 'url': url})
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(
                '[upload_files_for_enterprise_coupons] Raised an error while uploading the files,Message: %s',
                ex
            )
    return uploaded_files
