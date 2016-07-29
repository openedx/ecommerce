""" Payment-related URLs """
from django.conf.urls import url

from ecommerce.payment_processors.adyen import views

urlpatterns = [
    url(r'^adyen/notification/$', views.AdyenNotificationView.as_view(), name='adyen_notification'),
    url(r'^adyen/payment/$', views.AdyenPaymentView.as_view(), name='adyen_payment'),
]
