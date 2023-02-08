from oscar.core.loading import get_model
from rest_framework import serializers

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.api.serializers import BillingAddressSerializer, UserSerializer

Order = get_model('order', 'Order')


class MobileOrderSerializer(serializers.ModelSerializer):
    """Serializer for parsing order data for mobile apps."""
    billing_address = BillingAddressSerializer(allow_null=True)
    date_placed = serializers.DateTimeField(format=ISO_8601_FORMAT)
    discount = serializers.SerializerMethodField()
    payment_processor = serializers.SerializerMethodField()
    user = UserSerializer()

    def get_payment_processor(self, obj):
        try:
            return obj.sources.all()[0].source_type.name
        except IndexError:
            return None

    def get_discount(self, obj):
        try:
            discount = obj.discounts.all()[0]
            return str(discount.amount)
        except IndexError:
            return '0'

    class Meta:
        model = Order
        fields = (
            'billing_address',
            'currency',
            'date_placed',
            'discount',
            'number',
            'payment_processor',
            'status',
            'total_excl_tax',
            'user',
        )
