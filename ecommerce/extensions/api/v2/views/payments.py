"""HTTP endpoints for interacting with payments."""
from django.conf import settings
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_extensions.cache.decorators import cache_response

from ecommerce.extensions.api import serializers
from ecommerce.extensions.payment.helpers import get_processor_class


PAYMENT_PROCESSOR_CACHE_KEY = 'PAYMENT_PROCESSOR_LIST'
PAYMENT_PROCESSOR_CACHE_TIMEOUT = 60 * 30


class PaymentProcessorListView(generics.ListAPIView):
    """View that lists the available payment processors."""
    pagination_class = None
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.PaymentProcessorSerializer

    @cache_response(
        PAYMENT_PROCESSOR_CACHE_TIMEOUT,
        key_func=lambda *args, **kwargs: PAYMENT_PROCESSOR_CACHE_KEY,
        cache_errors=False,
    )
    def get(self, request):
        return super(PaymentProcessorListView, self).get(request)

    def get_queryset(self):
        """Fetch the list of payment processor classes based on Django settings."""
        processors = (get_processor_class(path) for path in settings.PAYMENT_PROCESSORS)
        return [processor for processor in processors if processor.is_enabled()]
