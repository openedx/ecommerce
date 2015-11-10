from django.conf.urls import url

from ecommerce.codes import views

urlpatterns = [

    # Declare all paths above this line to avoid dropping into the Course Admin Tool (which does its own routing)
    url(r'^(.*)$', views.CodeAppView.as_view(), name='app'),
]
