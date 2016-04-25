# noinspection PyUnresolvedReferences
from django.db import models


class CouponVouchers(models.Model):
    coupon = models.ForeignKey('catalogue.Product', related_name='coupon_vouchers')
    vouchers = models.ManyToManyField('voucher.Voucher', blank=True, related_name='coupon_vouchers')


class OrderVouchers(models.Model):
    order = models.ForeignKey('order.Order', related_name='order_vouchers')
    vouchers = models.ManyToManyField('voucher.Voucher', blank=True, related_name='order_vouchers')

# noinspection PyUnresolvedReferences
from oscar.apps.voucher.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
