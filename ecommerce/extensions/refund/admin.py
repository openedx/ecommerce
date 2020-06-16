

import waffle
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from rules.contrib.admin import ObjectPermissionsModelAdmin, ObjectPermissionsTabularInline

from ecommerce.extensions.refund.constants import REFUND_LIST_VIEW_SWITCH

Refund = get_model('refund', 'Refund')
RefundLine = get_model('refund', 'RefundLine')


class RefundLineInline(ObjectPermissionsTabularInline):
    model = RefundLine
    fields = ('order_line', 'line_credit_excl_tax', 'quantity', 'status', 'created', 'modified',)
    readonly_fields = ('order_line', 'line_credit_excl_tax', 'quantity', 'created', 'modified',)
    extra = 0


@admin.register(Refund)
class RefundAdmin(ObjectPermissionsModelAdmin):
    list_display = ('id', 'order', 'user', 'status', 'total_credit_excl_tax', 'currency', 'created', 'modified',)
    list_filter = ('status',)
    show_full_result_count = False

    fields = ('order', 'user', 'status', 'total_credit_excl_tax', 'currency', 'created', 'modified',)
    readonly_fields = ('order', 'user', 'total_credit_excl_tax', 'currency', 'created', 'modified',)
    inlines = (RefundLineInline,)

    def get_queryset(self, request):
        if not waffle.switch_is_active(REFUND_LIST_VIEW_SWITCH):
            # Translators: "Waffle" is the name of a third-party library. It should not be translated
            msg = _('Refund administration has been disabled due to the load on the database. '
                    'This functionality can be restored by activating the {switch_name} Waffle switch. '
                    'Be careful when re-activating this switch!').format(switch_name=REFUND_LIST_VIEW_SWITCH)

            self.message_user(request, msg, level=messages.WARNING)
            return Refund.objects.none()

        queryset = super(RefundAdmin, self).get_queryset(request)
        return queryset

    def get_object(self, request, object_id, from_field=None):
        """
        Return an instance matching the field and value provided, the primary
        key is used if no field is provided. Return ``None`` if no match is
        found or the object_id fails validation.
        """
        if not waffle.switch_is_active(REFUND_LIST_VIEW_SWITCH):
            # pylint: disable=protected-access
            field = Refund._meta.pk if from_field is None else Refund._meta.get_field(from_field)
            try:
                object_id = field.to_python(object_id)
                return Refund.objects.get(**{field.name: object_id})
            except (Refund.DoesNotExist, ValidationError, ValueError):
                return None

        return super(RefundAdmin, self).get_object(request, object_id, from_field=from_field)
