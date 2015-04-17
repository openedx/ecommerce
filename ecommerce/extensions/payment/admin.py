from django.contrib import admin
from oscar.core.loading import get_model


PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class PaymentProcessorResponseAdmin(admin.ModelAdmin):
    list_display = ('processor_name', 'transaction_id', 'basket', 'created')


admin.site.register(PaymentProcessorResponse, PaymentProcessorResponseAdmin)

# noinspection PyUnresolvedReferences
from oscar.apps.payment.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
