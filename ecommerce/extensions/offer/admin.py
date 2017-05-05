from oscar.apps.offer.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import


class RangeAdminExtended(admin.ModelAdmin):
    list_display = ('name', 'catalog', 'catalog_query', 'course_catalog', 'course_seat_types', 'program_uuid')
    raw_id_fields = ('catalog',)
    search_fields = ['name', 'course_catalog', 'program_uuid']


admin.site.unregister(Range)
admin.site.register(Range, RangeAdminExtended)
