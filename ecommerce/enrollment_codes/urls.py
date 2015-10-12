from django.conf.urls import url

from ecommerce.enrollment_codes import views

urlpatterns = [
    url(r'^(.*)$', views.EnrollmentCodesAppView.as_view(), name='app')
]
