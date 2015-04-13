"""Serializers for Payment data."""
# pylint: disable=abstract-method
from rest_framework import serializers


class TransactionSerializer(serializers.Serializer):
    """Serializes a transaction. """
    txn_type = serializers.CharField(max_length=128)
    amount = serializers.DecimalField(decimal_places=2, max_digits=12)
    reference = serializers.CharField(max_length=128)
    status = serializers.CharField(max_length=128)
    date_created = serializers.DateTimeField()


class SourceTypeSerializer(serializers.Serializer):
    """Serializes the payment source type. """
    name = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=128)


class SourceSerializer(serializers.Serializer):
    """Serializes a payment source. """
    source_type = SourceTypeSerializer()
    transactions = TransactionSerializer(many=True)
    currency = serializers.CharField(max_length=12)
    amount_allocated = serializers.DecimalField(decimal_places=2, max_digits=12)
    amount_debited = serializers.DecimalField(decimal_places=2, max_digits=12)
    amount_refunded = serializers.DecimalField(decimal_places=2, max_digits=12)
    reference = serializers.CharField(max_length=128)
    label = serializers.CharField(max_length=128)
