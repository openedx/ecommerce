

from django.conf.urls import include, url

urlpatterns = [
    url(r'^payment/', include(('ecommerce.bff.payment.urls', 'payment'))),
    url(r'subscriptions/', include(('ecommerce.bff.subscriptions.urls', 'subscriptions')))

]
