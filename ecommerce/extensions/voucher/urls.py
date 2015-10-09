from django.conf.urls import url

from ecommerce.extensions.voucher import views

urlpatterns = [
    url(r'^$', views.EnrollmentCodes, name='app'),
    url(r'^new/$', views.NewEnrollmentCode, name='new'),
]