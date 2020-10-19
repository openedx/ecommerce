

from oscar.apps.offer.admin import *  # pylint: disable=unused-import,wildcard-import,unused-wildcard-import
from oscar.core.loading import get_model

admin.site.unregister(ConditionalOffer)
admin.site.unregister(Condition)
admin.site.unregister(Range)

OfferAssignment = get_model('offer', 'OfferAssignment')
OfferAssignmentEmailAttempt = get_model('offer', 'OfferAssignmentEmailAttempt')
CodeAssignmentNudgeEmailTemplates = get_model('offer', 'CodeAssignmentNudgeEmailTemplates')


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
                    'condition', 'benefit', 'total_discount', 'partner')
    raw_id_fields = ('benefit', 'condition',)
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'partner', 'offer_type', 'condition',
                       'benefit', 'start_datetime', 'end_datetime', 'priority', 'exclusive')
        }),
        ('Usage', {
            'fields': ('total_discount', 'num_orders')
        }),
    )


@admin.register(OfferAssignment)
class OfferAssignmentAdmin(admin.ModelAdmin):
    """
    Django admin model for `OfferAssignment`
    """
    class Meta:
        model = OfferAssignment

    list_display = ('code', 'user_email', 'status', 'offer', 'voucher_application')
    search_fields = ('code', 'user_email', 'status')


@admin.register(OfferAssignmentEmailAttempt)
class OfferAssignmentEmailAttemptAdmin(admin.ModelAdmin):
    """
    Django admin model for `OfferAssignmentEmailAttempt`
    """
    class Meta:
        model = OfferAssignmentEmailAttempt

    list_display = ('send_id', 'offer_assignment')
    search_fields = ('send_id',)
    fields = ('send_id', 'offer_assignment')


@admin.register(CodeAssignmentNudgeEmailTemplates)
class CodeAssignmentNudgeEmailTemplatesAdmin(admin.ModelAdmin):
    """
    Django admin model for `CodeAssignmentNudgeEmailTemplates`
    """
    class Meta:
        model = CodeAssignmentNudgeEmailTemplates

    list_display = ('id', 'email_type', 'created', 'modified', 'active')
