

import waffle
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from oscar.apps.order.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
from oscar.core.loading import get_model

from ecommerce.extensions.order.constants import ORDER_LIST_VIEW_SWITCH

MarkOrdersStatusCompleteConfig = get_model('order', 'MarkOrdersStatusCompleteConfig')

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
    list_display = ('partner',) + OrderAdmin.list_display
    readonly_fields = ('basket',) + OrderAdmin.readonly_fields
    show_full_result_count = False

    def get_queryset(self, request):
        if not waffle.switch_is_active(ORDER_LIST_VIEW_SWITCH):
            # Translators: "Waffle" is the name of a third-party library. It should not be translated
            msg = _('Order administration has been disabled due to the load on the database. '
                    'This functionality can be restored by activating the {switch_name} Waffle switch. '
                    'Be careful when re-activating this switch!').format(switch_name=ORDER_LIST_VIEW_SWITCH)

            self.message_user(request, msg, level=messages.WARNING)
            return Order.objects.none()

        queryset = super(OrderAdminExtended, self).get_queryset(request)
        queryset = queryset.select_related('partner', 'site', 'user', 'basket', )
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


admin.site.register(MarkOrdersStatusCompleteConfig)
