from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from ecommerce.invoice.models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'basket', 'order', 'business_client', 'state',)
    list_filter = ('state',)
    search_fields = ['order__number', 'business_client__name']
