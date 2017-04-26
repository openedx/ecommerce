from django.conf.urls import url

from ecommerce.programs import views

urlpatterns = [
    url(r'^(.*)$', views.ProgramAppView.as_view(), name='app'),
]
