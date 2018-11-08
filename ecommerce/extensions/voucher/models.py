import datetime
import logging
import waffle

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from oscar.apps.voucher.abstract_models import AbstractVoucher  # pylint: disable=ungrouped-imports

from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH

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

    @property
    def original_offer(self):
        try:
            return self.offers.filter(condition__range__isnull=False)[0]
        except (IndexError, ObjectDoesNotExist):
            return self.offers.order_by('date_created')[0]

    @property
    def enterprise_offer(self):
        try:
            return self.offers.get(condition__enterprise_customer_uuid__isnull=False)
        except ObjectDoesNotExist:
            return None
        except MultipleObjectsReturned:
            logger.exception('There is more than one enterprise offer associated with voucher %s!', self.id)
            return self.offers.filter(condition__enterprise_customer_uuid__isnull=False)[0]

    @property
    def best_offer(self):
        # If the ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH is inactive, return offer containing a range
        if not waffle.switch_is_active(ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH):
            return self.original_offer
        # If the switch is enabled, return the enterprise offer if it exists.
        return self.enterprise_offer or self.original_offer

from oscar.apps.voucher.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
