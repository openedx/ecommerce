from django.conf.urls import url

from ecommerce.enrollment_codes import views

urlpatterns = [

    # Declare all paths above this line to avoid dropping into the Course Admin Tool (which does its own routing)
    url(r'^(.*)$', views.EnrollmentCodeAppView.as_view(), name='enrollment_app'),
]
