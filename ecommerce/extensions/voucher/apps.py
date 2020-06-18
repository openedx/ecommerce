

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from oscar.apps.voucher import apps


class VoucherConfig(apps.VoucherConfig):
    name = 'ecommerce.extensions.voucher'

    def ready(self):  # pragma: no cover
        super().ready()
        if settings.VOUCHER_CODE_LENGTH < 1:
            raise ImproperlyConfigured("VOUCHER_CODE_LENGTH must be a positive number.")
