"""Payment Extension Serializers. """

from rest_framework import serializers

from ecommerce.extensions.payment.models import SDNCheckFailure


class SDNCheckFailureSerializer(serializers.ModelSerializer):
    """
    Serializer for SDNCheckFailure model.
    """

    class Meta:
        model = SDNCheckFailure
        fields = '__all__'
