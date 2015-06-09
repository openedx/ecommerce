from oscar.apps.partner.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
from simple_history.admin import SimpleHistoryAdmin


class StockRecordAdminExtended(SimpleHistoryAdmin):
    list_display = ('product', 'partner', 'partner_sku', 'price_excl_tax', 'cost_price', 'num_in_stock')
    list_filter = ('partner',)


admin.site.unregister(StockRecord)
admin.site.register(StockRecord, StockRecordAdminExtended)
