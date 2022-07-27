from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter

from ecommerce.extensions.basket.views import ExecutiveEducation2UAPIViewSet

router = DefaultRouter()
router.register('', ExecutiveEducation2UAPIViewSet, basename='executive_education_2u')
urlpatterns = [
    url(r'^v0/', include((router.urls, 'v0'))),
]
