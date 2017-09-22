from oscar.apps.offer.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import

admin.site.unregister(ConditionalOffer)
admin.site.unregister(Condition)
admin.site.unregister(Range)


@admin.register(Range)
class RangeAdminExtended(admin.ModelAdmin):
    list_display = ('name', 'catalog', 'catalog_query', 'course_catalog', 'course_seat_types')
    raw_id_fields = ('catalog',)
    search_fields = ['name', 'course_catalog']


@admin.register(Condition)
class ConditionAdminExtended(ConditionAdmin):
    list_display = ('type', 'value', 'range', 'program_uuid')


@admin.register(ConditionalOffer)
class ConditionalOfferAdminExtended(ConditionalOfferAdmin):
    list_display = ('name', 'offer_type', 'start_datetime', 'end_datetime',
                    'condition', 'benefit', 'total_discount', 'site')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'site', 'offer_type', 'condition',
                       'benefit', 'start_datetime', 'end_datetime', 'priority')
        }),
        ('Usage', {
            'fields': ('total_discount', 'num_orders')
        }),
    )
