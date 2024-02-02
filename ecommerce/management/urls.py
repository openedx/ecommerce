

from django.urls import path

from ecommerce.management import views

urlpatterns = [
    path('', views.ManagementView.as_view(), name='index'),
]
