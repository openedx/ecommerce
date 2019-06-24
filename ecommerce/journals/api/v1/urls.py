""" API v1 URLs. """
from __future__ import absolute_import

from rest_framework.routers import DefaultRouter

from .views import JournalProductViewSet

router = DefaultRouter()
router.register(r'journals', JournalProductViewSet, base_name='journals')
urlpatterns = router.urls
