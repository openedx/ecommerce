"""Serializers for order and line item data."""
# pylint: disable=abstract-method
from oscar.core.loading import get_model
from rest_framework import serializers

from ecommerce.extensions.payment.constants import ISO_8601_FORMAT

BillingAddress = get_model('order', 'BillingAddress')
Line = get_model('order', 'Line')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')
Refund = get_model('refund', 'Refund')


class BillingAddressSerializer(serializers.ModelSerializer):
    """Serializes a Billing Address. """
    city = serializers.CharField(max_length=255, source='line4')

    class Meta(object):
        model = BillingAddress
        fields = ('first_name', 'last_name', 'line1', 'line2', 'postcode', 'state', 'country', 'city')


class ProductAttributeValueSerializer(serializers.Serializer):
    """ Serializer for ProductAttributeValue objects. """
    name = serializers.SerializerMethodField()
    value = serializers.CharField()
    type = serializers.SerializerMethodField()

    def get_name(self, instance):
        return instance.attribute.name

    def get_type(self, instance):
        return instance.attribute.type

    class Meta(object):
        model = ProductAttributeValue
        fields = ('name', 'value', 'type')


class ProductSerializer(serializers.ModelSerializer):
    """ Serializer for Products. """
    attribute_values = ProductAttributeValueSerializer(many=True)

    class Meta(object):
        model = Product
        fields = ('attribute_values',)


class LineSerializer(serializers.ModelSerializer):
    """Serializer for parsing line item data."""
    product = ProductSerializer()

    class Meta(object):
        model = Line
        fields = ('title', 'quantity', 'description', 'status', 'line_price_excl_tax', 'unit_price_excl_tax', 'product')


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for parsing order data."""
    date_placed = serializers.DateTimeField(format=ISO_8601_FORMAT)
    lines = LineSerializer(many=True)
    billing_address = BillingAddressSerializer(allow_null=True)

    class Meta(object):
        model = Order
        fields = ('number', 'date_placed', 'status', 'currency', 'total_excl_tax', 'lines', 'billing_address')


class PaymentProcessorSerializer(serializers.Serializer):
    """ Serializer to use with instances of processors.BasePaymentProcessor """

    def to_representation(self, instance):
        """ Serialize instances as a string instead of a mapping object. """
        return instance.NAME


class RefundSerializer(serializers.ModelSerializer):
    """ Serializer for Refund objects. """

    class Meta(object):
        model = Refund
