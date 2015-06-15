from django.conf import settings
from django.conf.urls import patterns, url

from ecommerce.credit.views import Checkout


urlpatterns = patterns(
    '',
    url(r'^checkout/{course}/$'.format(course=settings.COURSE_ID_PATTERN),
        Checkout.as_view(), name='checkout'),
)
