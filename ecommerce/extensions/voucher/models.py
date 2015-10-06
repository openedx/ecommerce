from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.voucher.abstract_models import AbstractVoucher


class Voucher(AbstractVoucher):
    course_id = models.CharField(_('Course ID'), blank=True, max_length=255)


from oscar.apps.voucher.models import *  # noqa
