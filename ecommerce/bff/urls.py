

from django.conf.urls import include, url

urlpatterns = [
    url(r'^payment/', include(('ecommerce.bff.payment.urls', 'payment'))),
    url(r'^executive-education-2u/', include(('ecommerce.bff.executive_education_2u.urls', 'executive_education_2u')))
]
