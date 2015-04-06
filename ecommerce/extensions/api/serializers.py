"""Serializers for order and line item data."""
# pylint: disable=abstract-method
from decimal import Decimal as D

from rest_framework import serializers

from ecommerce.extensions.payment.serializers import SourceSerializer


class CountrySerializer(serializers.Serializer):
    """Serializes a country, related to a billing address. """
    printable_name = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=128)
    is_shipping_country = serializers.BooleanField()


class BillingAddressSerializer(serializers.Serializer):
    """Serializes a Billing Address. """
    title = serializers.CharField(max_length=64)
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    line1 = serializers.CharField(max_length=255)
    line2 = serializers.CharField(max_length=255)
    line3 = serializers.CharField(max_length=255)
    line4 = serializers.CharField(max_length=255)
    state = serializers.CharField(max_length=255)
    postcode = serializers.CharField(max_length=64)
    country = CountrySerializer()


class LinesSerializer(serializers.Serializer):
    """Serializer for parsing line item data."""
    title = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField(min_value=0)
    description = serializers.CharField()
    status = serializers.CharField(max_length=255)
    line_price_excl_tax = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        min_value=D('0.00')
    )
    unit_price_excl_tax = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        min_value=D('0.00')
    )


class OrderSerializer(serializers.Serializer):
    """Serializer for parsing order data."""
    number = serializers.CharField(max_length=128)
    date_placed = serializers.DateTimeField()
    status = serializers.CharField(max_length=100)
    sources = SourceSerializer(many=True)
    currency = serializers.CharField(min_length=3, max_length=3)
    total_excl_tax = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        min_value=D('0.00')
    )
    lines = LinesSerializer(many=True)
    billing_address = BillingAddressSerializer(allow_null=True)
    payment_processor = serializers.CharField(max_length=32)
