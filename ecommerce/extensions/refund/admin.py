from django.contrib import admin
from oscar.core.loading import get_model

Refund = get_model('refund', 'Refund')


class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'status', 'total_credit_excl_tax', 'currency')
    list_filter = ('status',)


admin.site.register(Refund, RefundAdmin)
