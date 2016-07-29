""" Payment-related URLs """
from django.conf.urls import url

from ecommerce.payment_processors.cybersource import views

urlpatterns = [
    url(r'^cybersource/notify/$', views.CybersourceNotifyView.as_view(), name='cybersource_notify'),
]
