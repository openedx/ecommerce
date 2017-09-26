from rest_framework import generics
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ecommerce.enterprise.utils import get_enterprise_customers


class EnterpriseCustomerViewSet(generics.GenericAPIView):

    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get(self, request):
        site = request.site
        return Response(data={'results': get_enterprise_customers(site)})
