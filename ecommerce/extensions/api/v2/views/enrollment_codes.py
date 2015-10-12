"""HTTP endpoints for interacting with enrollment codes."""
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.enrollment_codes.models import EnrollmentCode
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet
from ecommerce.extensions.api import serializers


class EnrollmentCodeViewSet(NonDestroyableModelViewSet):
    queryset = EnrollmentCode.objects.all()
    serializer_class = serializers.EnrollmentCodeSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)