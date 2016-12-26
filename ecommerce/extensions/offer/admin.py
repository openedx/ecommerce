from oscar.apps.offer.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import


class RangeAdminExtended(admin.ModelAdmin):
    list_display = ('name', 'catalog', 'course_catalog',)
    raw_id_fields = ('catalog',)
    search_fields = ['name', 'course_catalog']


admin.site.unregister(Range)
admin.site.register(Range, RangeAdminExtended)
