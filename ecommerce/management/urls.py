

from django.conf.urls import url

from ecommerce.management import views

urlpatterns = [
    url(r'^$', views.ManagementView.as_view(), name='index'),
]
