

from django.urls import include, path

urlpatterns = [
    path('payment/', include(('ecommerce.bff.payment.urls', 'payment'))),
    path('subscriptions/', include(('ecommerce.bff.subscriptions.urls', 'subscriptions')))

]
