import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings  # lint-amnesty, pylint: disable=unused-import

from ecommerce.extensions.voucher.models import Voucher

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def update_voucher_names(self, vouchers):
    for voucher in vouchers:
        if not f"{voucher.id} -" in voucher.name:
            updated_name = f"{voucher.id} - {voucher.name}"
            try:
                if len(updated_name) > 128:
                    logger.warning("Name length exceeds 128 characters for voucher id %d. Truncating...", voucher.id)
                    updated_name = updated_name[:128]
                
                voucher.name = updated_name
                voucher.save()
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error updating voucher name %d: %s", voucher.id, exc)
