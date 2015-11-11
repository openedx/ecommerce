"""HTTP endpoints for interacting with invoices."""
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import generics

from ecommerce.invoice.models import Invoice
from ecommerce.extensions.api import serializers


class InvoiceListView(generics.ListAPIView):
    """
    Endpoint for listing invoices.
    """
    queryset = Invoice.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser,)
    serializer_class = serializers.InvoiceSerializer
