from django.conf.urls import url

from ecommerce.receipts import views

urlpatterns = [
    url(r'^(.*)$', views.ReceiptsView.as_view(), name='app'),
]

