from oscar.apps.basket.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import

Basket = get_model('basket', 'basket')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

admin.site.unregister((Basket, Line,))


class PaymentProcessorResponseInline(admin.TabularInline):
    model = PaymentProcessorResponse
    extra = 0
    can_delete = False
    readonly_fields = ('id', 'processor_name', 'transaction_id', 'created', 'response')

    def has_add_permission(self, request):
        # Users are not allowed to add PaymentProcessorResponse objects
        return False


@admin.register(Basket)
class BasketAdminExtended(BasketAdmin):
    inlines = (LineInline, PaymentProcessorResponseInline,)
    show_full_result_count = False


@admin.register(Line)
class LineAdminExtended(LineAdmin):
    show_full_result_count = False
