""" Payment-related URLs """
from django.conf.urls import url

from ecommerce.adyen import views


app_name = 'adyen'
urlpatterns = [
    url(r'^notification/$', views.AdyenNotificationView.as_view(), name='notification'),
    url(r'^payment/$', views.AdyenPaymentView.as_view(), name='payment'),
]
