import datetime
import logging

from django.db import models
from oscar.apps.voucher.abstract_models import AbstractVoucher  # pylint: disable=ungrouped-imports

from ecommerce.core.utils import log_message_and_raise_validation_error

logger = logging.getLogger(__name__)


class CouponVouchers(models.Model):
    UPDATEABLE_VOUCHER_FIELDS = [
        'end_datetime',
        'start_datetime',
        'name'
    ]
    coupon = models.ForeignKey('catalogue.Product', related_name='coupon_vouchers', on_delete=models.CASCADE)
    vouchers = models.ManyToManyField('voucher.Voucher', blank=True, related_name='coupon_vouchers')


class OrderLineVouchers(models.Model):
    line = models.ForeignKey('order.Line', related_name='order_line_vouchers', on_delete=models.CASCADE)
    vouchers = models.ManyToManyField('voucher.Voucher', related_name='order_line_vouchers')


class Voucher(AbstractVoucher):
    def save(self, *args, **kwargs):
        self.clean()
        super(Voucher, self).save(*args, **kwargs)  # pylint: disable=bad-super-call

    def clean(self):
        self.clean_code()
        self.clean_datetimes()
        super(Voucher, self).clean()  # pylint: disable=bad-super-call

    def clean_code(self):
        if not self.code:
            log_message_and_raise_validation_error('Failed to create Voucher. Voucher code must be set.')
        if not self.code.isalnum():
            log_message_and_raise_validation_error(
                'Failed to create Voucher. Voucher code must contain only alphanumeric characters.'
            )

    def clean_datetimes(self):
        if not (self.end_datetime and self.start_datetime):
            log_message_and_raise_validation_error(
                'Failed to create Voucher. Voucher start and end datetime fields must be set.'
            )

        if not (isinstance(self.end_datetime, datetime.datetime) and
                isinstance(self.start_datetime, datetime.datetime)):
            log_message_and_raise_validation_error(
                'Failed to create Voucher. Voucher start and end datetime fields must be type datetime.'
            )

    @classmethod
    def does_exist(cls, code):
        try:
            Voucher.objects.get(code=code)
            return True
        except Voucher.DoesNotExist:
            return False


from oscar.apps.voucher.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
