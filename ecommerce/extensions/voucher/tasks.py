import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def update_voucher_names_task(self, vouchers):  # pylint: disable=unused-argument
    """
    Wrapper to allow update_voucher_names be run as a celery task.
    """
    update_voucher_names(vouchers)


def update_voucher_names(vouchers):
    """
    Update voucher names to be unique, and no more than 128 chars long.
    """
    for voucher in vouchers:
        if f"{voucher.id} -" not in voucher.name:
            updated_name = f"{voucher.id} - {voucher.name}"
            try:
                if len(updated_name) > 128:
                    logger.warning("Name length exceeds 128 characters for voucher id %d. Truncating...", voucher.id)
                    updated_name = updated_name[:128]

                voucher.name = updated_name
                voucher.save()
            except Exception as exc:  # pylint: disable=broad-except; # pragma: no cover
                logger.exception("Error updating voucher name %d: %s", voucher.id, exc)
