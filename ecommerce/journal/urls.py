from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('ecommerce.journal.api.urls', namespace='api')),
]
