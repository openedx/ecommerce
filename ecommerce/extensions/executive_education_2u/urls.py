
from rest_framework.routers import DefaultRouter

from ecommerce.extensions.executive_education_2u.views import ExecutiveEducation2UViewSet

router = DefaultRouter()
router.register(r'', ExecutiveEducation2UViewSet, basename='executive_education_2u')
urlpatterns = router.urls
