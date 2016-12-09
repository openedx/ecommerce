import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.voucher.abstract_models import AbstractVoucher

logger = logging.getLogger(__name__)


class CouponVouchers(models.Model):
    UPDATEABLE_VOUCHER_FIELDS = [
        'end_datetime',
        'start_datetime',
        'name'
    ]
    coupon = models.ForeignKey('catalogue.Product', related_name='coupon_vouchers')
    vouchers = models.ManyToManyField('voucher.Voucher', blank=True, related_name='coupon_vouchers')


class OrderLineVouchers(models.Model):
    line = models.ForeignKey('order.Line', related_name='order_line_vouchers')
    vouchers = models.ManyToManyField('voucher.Voucher', related_name='order_line_vouchers')


class Voucher(AbstractVoucher):
    def save(self, *args, **kwargs):
        self.clean()
        super(Voucher, self).save(*args, **kwargs)  # pylint: disable=bad-super-call

    def clean(self):
        if not self.code:
            logger.exception('Failed to create Voucher. Voucher code must be set.')
            raise ValidationError(_('Voucher code must be set.'))
        if not self.code.isalnum():
            logger.exception('Failed to create Voucher. Voucher code must contain only alphanumeric characters.')
            raise ValidationError(_('Voucher code must contain only alphanumeric characters.'))


from oscar.apps.voucher.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
