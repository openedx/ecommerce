from oscar.apps.order.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import

Order = get_model('order', 'Order')


class OrderAdminExtended(OrderAdmin):
    readonly_fields = ('basket',) + OrderAdmin.readonly_fields


admin.site.unregister(Order)
admin.site.register(Order, OrderAdminExtended)
