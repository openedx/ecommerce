
import logging

from celery import shared_task
from django.db.utils import IntegrityError

from ecommerce.extensions.voucher.utils import create_vouchers

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def create_vouchers_and_attach_to_product(
        benefit_type,
        benefit_value,
        catalog,
        catalog_query,
        code,
        coupon_product,
        course_catalog,
        course_seat_types,
        email_domains,
        end_datetime,
        enterprise_customer,
        enterprise_customer_catalog,
        max_uses,
        note,
        title,
        quantity,
        start_datetime,
        voucher_type,
        program_uuid,
        site,
        sales_force_id
):
    vouchers = []
    try:
        vouchers = create_vouchers(
            benefit_type=benefit_type,
            benefit_value=benefit_value,
            catalog=catalog,
            catalog_query=catalog_query,
            code=code or None,
            coupon=coupon_product,
            course_catalog=course_catalog,
            course_seat_types=course_seat_types,
            email_domains=email_domains,
            end_datetime=end_datetime,
            enterprise_customer=enterprise_customer,
            enterprise_customer_catalog=enterprise_customer_catalog,
            max_uses=max_uses,
            name=title,
            quantity=int(quantity),
            start_datetime=start_datetime,
            voucher_type=voucher_type,
            program_uuid=program_uuid,
            site=site
        )
    except IntegrityError:
        logger.exception('Failed to create vouchers for [%s] coupon.', coupon_product.title)

    from ecommerce.extensions.catalogue.utils import attach_vouchers_to_coupon_product
    if vouchers:
        attach_vouchers_to_coupon_product(coupon_product, vouchers, note, enterprise_id=enterprise_customer,
                                          sales_force_id=sales_force_id)
