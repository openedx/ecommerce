""" JournalViewSet """
from oscar.core.loading import get_model
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from ecommerce.journal.api.serializers import JournalProductSerializer, JournalProductUpdateSerializer

Product = get_model('catalogue', 'Product')


class JournalProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows journals to be viewed or edited.
    """
    # this does lookup based on UUID value of productattributevalue table
    lookup_field = 'attribute_values__value_text'
    queryset = Product.objects.filter(product_class__name='Journal')
    serializer_class = JournalProductSerializer
    permission_classes = (IsAdminUser,)

    def get_serializer_class(self):
        serializer_class = self.serializer_class

        if self.request and hasattr(self.request, 'method'):
            if self.request.method == 'PATCH' or self.request.method == 'PUT':
                serializer_class = JournalProductUpdateSerializer

        return serializer_class
