from __future__ import absolute_import

from django.conf.urls import include, url

urlpatterns = [
    url(r'^payment/', include(('ecommerce.bff.payment.urls', 'payment'))),
]
