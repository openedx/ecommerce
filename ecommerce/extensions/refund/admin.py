from django.contrib import admin
from oscar.core.loading import get_model

Refund = get_model('refund', 'Refund')
RefundLine = get_model('refund', 'RefundLine')


class RefundLineInline(admin.TabularInline):
    model = RefundLine
    fields = ('order_line', 'line_credit_excl_tax', 'quantity', 'status', 'created', 'modified',)
    readonly_fields = ('order_line', 'line_credit_excl_tax', 'quantity', 'created', 'modified',)
    extra = 0


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'status', 'total_credit_excl_tax', 'currency', 'created', 'modified',)
    list_filter = ('status',)
    show_full_result_count = False

    fields = ('order', 'user', 'status', 'total_credit_excl_tax', 'currency', 'created', 'modified',)
    readonly_fields = ('order', 'user', 'total_credit_excl_tax', 'currency', 'created', 'modified',)
    inlines = (RefundLineInline,)
