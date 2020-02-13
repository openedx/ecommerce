from __future__ import absolute_import

import crum

import datetime
import logging

from jsonfield.fields import JSONField
from django_extensions.db.models import TimeStampedModel
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.voucher.abstract_models import (  # pylint: disable=ungrouped-imports
    AbstractVoucher,
    AbstractVoucherApplication
)
from simple_history.models import HistoricalRecords
from oscar.apps.voucher.abstract_models import AbstractVoucher  # pylint: disable=ungrouped-imports

from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.enterprise.constants import COUPON_ERRORS
from ecommerce.extensions.offer.constants import OFFER_ASSIGNMENT_REVOKED, OFFER_MAX_USES_DEFAULT, OFFER_REDEEMED

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
    SINGLE_USE, MULTI_USE, ONCE_PER_CUSTOMER, MULTI_USE_PER_CUSTOMER = (
        'Single use', 'Multi-use', 'Once per customer', 'Multi-use-per-Customer')
    USAGE_CHOICES = (
        (SINGLE_USE, _("Can be used once by one customer")),
        (MULTI_USE, _("Can be used multiple times by multiple customers")),
        (ONCE_PER_CUSTOMER, _("Can only be used once per customer")),
        (MULTI_USE_PER_CUSTOMER, _("Can be used multiple times by one customer")),
    )
    usage = models.CharField(_("Usage"), max_length=128,
                             choices=USAGE_CHOICES, default=MULTI_USE)

    def is_available_to_user(self, user=None):
        is_available, message = super(Voucher, self).is_available_to_user(user)  # pylint: disable=bad-super-call

        if self.usage == self.MULTI_USE_PER_CUSTOMER:
            is_available = True
            message = ''
            applications = self.applications.filter(voucher=self).exclude(user=user)
            if applications.exists():
                is_available = False
                message = _('This voucher is assigned to another user.')

        return is_available, message

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
        return self.enterprise_offer or self.original_offer

    @property
    def slots_available_for_assignment(self):
        """
        Calculate the number of available slots left for this voucher.
        A slot is a potential redemption of the voucher.
        """
        enterprise_offer = self.enterprise_offer
        # Assignment is only valid for Vouchers linked to an enterprise offer.
        if not enterprise_offer:
            return None

        # Find the number of OfferAssignments that already exist that are not redeemed or revoked.
        # Redeemed OfferAssignments are excluded in favor of using num_orders on this voucher.
        num_assignments = enterprise_offer.offerassignment_set.filter(code=self.code).exclude(
            status__in=[OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]
        ).count()

        return self.calculate_available_slots(enterprise_offer.max_global_applications, num_assignments)

    def calculate_available_slots(self, max_global_applications, num_assignments):
        """
        Calculate the number of available slots left for this voucher.
        """
        # If this a Single use or Multi use per customer voucher,
        # it must have no orders or existing assignments to be assigned.
        if self.usage in (self.SINGLE_USE, self.MULTI_USE_PER_CUSTOMER):
            if self.num_orders or num_assignments:
                return 0
            return max_global_applications or 1
        offer_max_uses = max_global_applications or OFFER_MAX_USES_DEFAULT
        return offer_max_uses - (self.num_orders + num_assignments)


class VoucherApplication(AbstractVoucherApplication):
    history = HistoricalRecords()


class CouponTrace(TimeStampedModel):
    user = models.ForeignKey('core.User', db_index=True)
    course = models.ForeignKey('courses.Course', db_index=True, blank=True, null=True)
    coupon_code = models.CharField(max_length=128, db_index=True)
    learner_enterprise_uuid = models.UUIDField(blank=True, null=True)
    learner_enterprise_name = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    metadata = JSONField(default={}, blank=True, null=True)

    @classmethod
    def create(cls, coupon_error_code, basket=None, extended_message=None, **kwargs):
        from ecommerce.enterprise.utils import (
            get_enterprise_id_for_user, get_enterprise_customer, get_enterprise_catalog_config
        )

        # Need to add some unique identifier for same request
        coupon_code = kwargs.get('coupon_code')
        current_site = kwargs.get('current_site')
        course = kwargs.get('product').course if kwargs.get('product') else None
        user = basket.owner if basket and basket.owner else kwargs.get('user')

        message = COUPON_ERRORS.get(coupon_error_code)
        if extended_message:
            message = "{message} because {extended_message}".format(message=message, extended_message=extended_message)

        if not course and not basket.is_empty and basket.all_lines():
            course = basket.all_lines()[0].product.course if basket.all_lines()[0].product else None

        if not current_site:
            current_site = basket.site if basket and basket.site else crum.get_current_request().site

        if not user:
            user = crum.get_current_request().user

        enterprise_uuid, enterprise_catalog_uuid, coupon_end_datetime, coupon_code = cls.get_enterprise_coupon_data(
            basket, coupon_code
        )

        enterprise_customer_uuid = kwargs.get('enterprise_customer_uuid') or enterprise_uuid
        enterprise_catalog_uuid = kwargs.get('enterprise_catalog_uuid') or enterprise_catalog_uuid

        # fetch enterprise name
        learner_enterprise = get_enterprise_customer(current_site, enterprise_customer_uuid)
        learner_enterprise_name = learner_enterprise['name'] if learner_enterprise else None

        # fetch enterprise catalog content filter
        enterprise_catalog_content_filter = {}
        if enterprise_catalog_uuid:
            enterprise_catalog_content_filter = get_enterprise_catalog_config(
                current_site, 'enterprise_catalog_uuid'
            )['content_filter']

        metadata = {
            'coupon_end_datetime': coupon_end_datetime,
            'enterprise_catalog_content_filter': enterprise_catalog_content_filter,
        }

        cls(
            user=user,
            course=course,
            coupon_code=coupon_code,
            learner_enterprise_uuid=enterprise_customer_uuid,
            learner_enterprise_name=learner_enterprise_name,
            message=message,
            metadata=metadata
        ).save()

    @staticmethod
    def get_enterprise_coupon_data(basket, coupon_code):
        coupon_end_datetime = None
        enterprise_customer_uuid = None
        enterprise_customer_catalog_uuid = None

        if not coupon_code:
            voucher = basket.vouchers.first()
            if voucher:
                coupon_end_datetime = voucher.end_datetime
                coupon_code = voucher.code
        else:
            voucher = Voucher.objects.get(coupon_code)
            coupon_end_datetime = voucher.end_datetime

        if voucher:
            condition = voucher.enterprise_offer.condition
            enterprise_customer_uuid = condition.enterprise_customer_uuid
            enterprise_customer_catalog_uuid = condition.enterprise_customer_catalog_uuid

        return enterprise_customer_uuid, enterprise_customer_catalog_uuid, coupon_end_datetime, coupon_code

from oscar.apps.voucher.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
