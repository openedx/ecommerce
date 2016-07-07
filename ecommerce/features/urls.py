from django.conf.urls import url

from ecommerce.features import views

urlpatterns = [
    url(r'^$', views.FeaturesList.as_view(), name='list'),
]
