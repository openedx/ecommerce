from oscar.apps.order.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import

admin.site.unregister((Order, Line, LinePrice, PaymentEvent, OrderDiscount,))


@admin.register(Order)
class OrderAdminExtended(OrderAdmin):
    readonly_fields = ('basket',) + OrderAdmin.readonly_fields
    show_full_result_count = False


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
