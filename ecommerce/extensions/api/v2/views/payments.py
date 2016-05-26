"""HTTP endpoints for interacting with payments."""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_extensions.cache.decorators import cache_response

from ecommerce.extensions.api import serializers


PAYMENT_PROCESSOR_CACHE_KEY = 'PAYMENT_PROCESSOR_LIST'
PAYMENT_PROCESSOR_CACHE_TIMEOUT = 60 * 30


class PaymentProcessorListView(generics.ListAPIView):
    """List the available payment processors"""
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
        return [processor for name, processor in self.request.site.siteconfiguration.get_payment_processors().items()]
