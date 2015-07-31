from django.conf.urls import patterns, url

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.credit.views import Checkout


urlpatterns = patterns(
    '',
    url(r'^checkout/{course}/$'.format(course=COURSE_ID_PATTERN),
        Checkout.as_view(), name='checkout'),
)
