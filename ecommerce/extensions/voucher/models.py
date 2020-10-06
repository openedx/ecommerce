

import datetime
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.voucher.abstract_models import (  # pylint: disable=ungrouped-imports
    AbstractVoucher,
    AbstractVoucherApplication
)
from simple_history.models import HistoricalRecords

from ecommerce.core.utils import log_message_and_raise_validation_error
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
    is_public = models.BooleanField(
        verbose_name=_('Is Public Code Batch'),
        help_text=_('Should this code batch be public or private for assignment.'),
        blank=True,
        default=False
    )

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
        offers = self.offers.all()
        for offer in offers:
            if offer.condition.enterprise_customer_uuid:
                return offer
        return None

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
        assignments = enterprise_offer.offerassignment_set.all()
        num_assignments = 0
        for assignment in assignments:
            if assignment.code == self.code and assignment.status not in [OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED]:
                num_assignments += 1

        return self.calculate_available_slots(enterprise_offer.max_global_applications, num_assignments)

    @property
    def not_redeemed_assignment_ids(self):
        """Returns offer assignments ids for the voucher that are available for redemption."""
        enterprise_offer = self.enterprise_offer
        # Assignment is only valid for Vouchers linked to an enterprise offer.
        if not enterprise_offer:
            return None

        # To filter out redeemed assignments of the given voucher
        users_having_usages = []
        for application in self.applications.all():
            user_email = application.user.email
            users_having_usages.append(user_email)

        not_redeemed_assignments = []
        for assignment in enterprise_offer.offerassignment_set.all():
            if assignment.code == self.code \
                    and assignment.status not in [OFFER_REDEEMED, OFFER_ASSIGNMENT_REVOKED] \
                    and assignment.user_email not in users_having_usages:
                not_redeemed_assignments.append(assignment.id)

        return not_redeemed_assignments

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


from oscar.apps.voucher.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
