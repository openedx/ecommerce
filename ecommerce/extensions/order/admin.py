from oscar.apps.order.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import

admin.site.unregister((Order, Line, LinePrice, PaymentEvent, OrderDiscount,))


class LineInlineExtended(LineInline):
    raw_id_fields = ['stockrecord', 'product', ]

    def get_queryset(self, request):
        queryset = super(LineInlineExtended, self).get_queryset(request)
        queryset = queryset.select_related('partner', 'stockrecord', 'product', )
        return queryset


@admin.register(Order)
class OrderAdminExtended(OrderAdmin):
    inlines = [LineInlineExtended]
    readonly_fields = ('basket',) + OrderAdmin.readonly_fields
    show_full_result_count = False

    def get_queryset(self, request):
        queryset = super(OrderAdminExtended, self).get_queryset(request)
        queryset = queryset.select_related('site', 'user', 'basket', )
        return queryset


@admin.register(Line)
class LineAdminExtended(LineAdmin):
    show_full_result_count = False


@admin.register(LinePrice)
class LinePriceAdminExtended(LinePriceAdmin):
    show_full_result_count = False


@admin.register(PaymentEvent)
class PaymentEventAdminExtended(PaymentEventAdmin):
    show_full_result_count = False


@admin.register(OrderDiscount)
class OrderDiscountAdminExtended(OrderDiscountAdmin):
    show_full_result_count = False
