from django.contrib import admin
from oscar.core.loading import get_model


Refund = get_model('refund', 'Refund')
RefundLine = get_model('refund', 'RefundLine')


class RefundLineInline(admin.TabularInline):
    model = RefundLine


class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'status', 'total_credit_excl_tax', 'currency')
    list_filter = ('status',)
    inlines = (RefundLineInline,)


admin.site.register(Refund, RefundAdmin)
