""" API v1 URLs. """
from rest_framework.routers import DefaultRouter

from .views import JournalProductViewSet

router = DefaultRouter()
router.register(r'journals', JournalProductViewSet, base_name='journal')
urlpatterns = router.urls
