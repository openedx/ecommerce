from oscar.apps.offer.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import
from simple_history.admin import SimpleHistoryAdmin


class RangeAdminExtended(SimpleHistoryAdmin):
    list_display = ('name', 'catalog',)


admin.site.unregister(Range)
admin.site.register(Range, RangeAdminExtended)
