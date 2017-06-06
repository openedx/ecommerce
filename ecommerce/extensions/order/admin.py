import waffle
from oscar.apps.order.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import

from ecommerce.extensions.order.constants import ORDER_LIST_VIEW_SWITCH

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

    def changelist_view(self, request, extra_context=None):
        if not waffle.switch_is_active(ORDER_LIST_VIEW_SWITCH):
            self.change_list_template = 'admin/disable_change_list.html'
        else:
            self.change_list_template = None

        return super(OrderAdminExtended, self).changelist_view(request, extra_context)


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
