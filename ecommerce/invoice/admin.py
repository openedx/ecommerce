from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from ecommerce.invoice.models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(SimpleHistoryAdmin):
    pass
