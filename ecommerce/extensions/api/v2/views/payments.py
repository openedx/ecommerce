"""HTTP endpoints for interacting with payments."""
from django.conf import settings
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ecommerce.extensions.api import serializers
from ecommerce.extensions.payment.helpers import get_processor_class


class PaymentProcessorListView(generics.ListAPIView):
    """View that lists the available payment processors."""
    pagination_class = None
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.PaymentProcessorSerializer

    def get_queryset(self):
        """Fetch the list of payment processor classes based on Django settings."""
        return [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]
