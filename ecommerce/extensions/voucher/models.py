# noinspection PyUnresolvedReferences
from django.db import models


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

# noinspection PyUnresolvedReferences
from oscar.apps.voucher.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
