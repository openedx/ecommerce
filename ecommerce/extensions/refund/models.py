from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from oscar.core.utils import get_default_currency
from simple_history.models import HistoricalRecords

from ecommerce.extensions.refund.exceptions import InvalidStatus


class StatusMixin(object):
    pipeline_setting = None

    @property
    def pipeline(self):
        # NOTE: We use the property and getattr (instead of settings.XXX) so that we can properly override the
        # settings when testing.
        return getattr(settings, self.pipeline_setting)

    def available_statuses(self):
        """ Returns all possible statuses that this object can move to. """
        return self.pipeline.get(self.status, ())

    # pylint: disable=access-member-before-definition,attribute-defined-outside-init
    def set_status(self, new_status):
        """
        Set a new status for this object.

        If the requested status is not valid, then ``InvalidStatus`` is raised.
        """
        if new_status not in self.available_statuses():
            msg = " Transition from '{status}' to '{new_status}' is invalid for {model_name} {id}.".format(
                new_status=new_status,
                model_name=self.__class__.__name__.lower(),
                id=self.id,
                status=self.status
            )
            raise InvalidStatus(msg)

        self.status = new_status
        self.save()

    def __str__(self):
        return unicode(self.id)


class Refund(StatusMixin, TimeStampedModel):
    """Main refund model, used to represent the state of a refund."""
    order = models.ForeignKey('order.Order', related_name='refunds', verbose_name=_('Order'))
    user = models.ForeignKey('user.User', related_name='refunds', verbose_name=_('User'))
    total_credit_excl_tax = models.DecimalField(_('Total Credit (excl. tax)'), decimal_places=2, max_digits=12)
    currency = models.CharField(_("Currency"), max_length=12, default=get_default_currency)
    status = models.CharField(_('Status'), max_length=255)

    history = HistoricalRecords()
    pipeline_setting = 'OSCAR_REFUND_STATUS_PIPELINE'

    @classmethod
    def all_statuses(cls):
        """ Returns all possible statuses for a refund. """
        return list(getattr(settings, cls.pipeline_setting).keys())

    @property
    def num_items(self):
        """ Returns the number of items in this refund. """
        num_items = 0
        for line in self.lines.all():
            num_items += line.quantity
        return num_items


class RefundLine(StatusMixin, TimeStampedModel):
    """A refund line, used to represent the state of a single item as part of a larger Refund."""
    refund = models.ForeignKey('refund.Refund', related_name='lines', verbose_name=_('Refund'))
    order_line = models.ForeignKey('order.Line', related_name='refund_lines', verbose_name=_('Order Line'))
    line_credit_excl_tax = models.DecimalField(_('Line Credit (excl. tax)'), decimal_places=2, max_digits=12)
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)
    status = models.CharField(_('Status'), max_length=255)

    history = HistoricalRecords()
    pipeline_setting = 'OSCAR_REFUND_LINE_STATUS_PIPELINE'
