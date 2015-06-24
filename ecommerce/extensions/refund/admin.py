from django.contrib import admin
from oscar.core.loading import get_model


Refund = get_model('refund', 'Refund')
RefundLine = get_model('refund', 'RefundLine')


class RefundLineInline(admin.TabularInline):
    model = RefundLine
    fields = ('order_line', 'line_credit_excl_tax', 'quantity', 'status')
    readonly_fields = ('order_line', 'line_credit_excl_tax', 'quantity')
    extra = 0


class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'status', 'total_credit_excl_tax', 'currency')
    list_filter = ('status',)

    fields = ('order', 'user', 'status', 'total_credit_excl_tax', 'currency')
    readonly_fields = ('order', 'user', 'total_credit_excl_tax', 'currency')
    inlines = (RefundLineInline,)


admin.site.register(Refund, RefundAdmin)
