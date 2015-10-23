from pprint import pformat

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class PaymentProcessorResponseAdmin(admin.ModelAdmin):
    list_filter = ('processor_name',)
    search_fields = ('id', 'processor_name', 'transaction_id',)
    list_display = ('id', 'processor_name', 'transaction_id', 'basket_display_value', 'created')
    fields = ('processor_name', 'transaction_id', 'basket_display_value', 'formatted_response')
    readonly_fields = ('processor_name', 'transaction_id', 'basket_display_value', 'formatted_response')

    def basket_display_value(self, obj):
        return '{} - {}'.format(obj.basket.id, obj.basket)

    basket_display_value.short_description = _('Basket')

    def formatted_response(self, obj):
        pretty_response = pformat(obj.response)

        # Use format_html() to escape user-provided inputs, avoiding an XSS vulnerability.
        return format_html('<br><br><pre>{}</pre>', pretty_response)

    formatted_response.allow_tags = True


admin.site.register(PaymentProcessorResponse, PaymentProcessorResponseAdmin)

# noinspection PyUnresolvedReferences
from oscar.apps.payment.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
