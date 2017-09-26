from oscar.core.loading import get_model
from rest_framework import status, viewsets
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response

from ecommerce.extensions.api import serializers

StockRecord = get_model('partner', 'StockRecord')


class StockRecordViewSet(viewsets.ModelViewSet):
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    serializer_class = serializers.StockRecordSerializer

    def get_queryset(self):
        return StockRecord.objects.filter(partner=self.request.site.siteconfiguration.partner)

    def get_serializer_class(self):
        serializer_class = self.serializer_class

        if self.request.method == 'PUT':
            serializer_class = serializers.PartialStockRecordSerializerForUpdate

        return serializer_class

    def update(self, request, *args, **kwargs):
        """ Update a stock record. """
        allowed_fields = ['price_currency', 'price_excl_tax']
        if any([key not in allowed_fields for key in request.data.keys()]):
            return Response({
                'message': "Only the price_currency and price_excl_tax fields are allowed to be modified."
            }, status=status.HTTP_400_BAD_REQUEST)
        return super(StockRecordViewSet, self).update(request, *args, **kwargs)
