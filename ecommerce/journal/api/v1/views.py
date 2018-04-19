'''JournalViewSet'''
from oscar.core.loading import get_model
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from ecommerce.journal.api.serializers import JournalProductSerializer


Product = get_model('catalogue', 'Product')


class JournalProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows journals to be viewed or edited.
    """
    lookup_field = 'id'
    queryset = Product.objects.filter(product_class__name='Journal')
    serializer_class = JournalProductSerializer
    permission_classes = (IsAdminUser,)
