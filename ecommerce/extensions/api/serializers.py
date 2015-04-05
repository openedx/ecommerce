"""Serializers for order and line item data."""
# pylint: disable=abstract-method
from decimal import Decimal as D

from rest_framework import serializers


class LinesSerializer(serializers.Serializer):
    """Serializer for parsing line item data."""
    title = serializers.CharField()
    description = serializers.CharField()
    status = serializers.CharField()
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
    currency = serializers.CharField(min_length=3, max_length=3)
    total_excl_tax = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        min_value=D('0.00')
    )
    lines = LinesSerializer(many=True)
    payment_processor = serializers.CharField(max_length=32)
