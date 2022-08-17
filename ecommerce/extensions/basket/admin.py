

from oscar.apps.basket.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import

from ecommerce.extensions.basket.models import BasketAttribute, BasketAttributeType

Basket = get_model('basket', 'basket')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

admin.site.unregister((Basket, Line,))


class PaymentProcessorResponseInline(admin.TabularInline):
    model = PaymentProcessorResponse
    extra = 0
    can_delete = False
    readonly_fields = ('id', 'processor_name', 'transaction_id', 'created', 'response')

    # TODO: Remove pylint disable after Django 2.2 upgrade
    def has_add_permission(self, request, obj=None):  # pylint: disable=arguments-differ,unused-argument
        # Users are not allowed to add PaymentProcessorResponse objects
        return False


class BasketAttributeInLine(admin.TabularInline):
    model = BasketAttribute
    readonly_fields = ('id', 'attribute_type', 'value_text',)
    extra = 0

    # TODO: Remove pylint disable after Django 2.2 upgrade
    def has_add_permission(self, request, obj=None):  # pylint: disable=arguments-differ,unused-argument
        # Users are not allowed to add BasketAttribute objects
        return False


@admin.register(Basket)
class BasketAdminExtended(BasketAdmin):
    raw_id_fields = ('vouchers', )
    inlines = (LineInline, PaymentProcessorResponseInline, BasketAttributeInLine,)
    show_full_result_count = False


@admin.register(Line)
class LineAdminExtended(LineAdmin):
    show_full_result_count = False


@admin.register(BasketAttributeType)
class BasketAttributeTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)
    readonly_fields = ('id', 'name',)
