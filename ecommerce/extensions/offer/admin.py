from oscar.apps.offer.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import


class RangeAdminExtended(admin.ModelAdmin):
    list_display = ('name', 'catalog',)
    raw_id_fields = ('catalog',)


admin.site.unregister(Range)
admin.site.register(Range, RangeAdminExtended)
