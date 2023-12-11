

from django.urls import re_path

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.credit.views import Checkout

urlpatterns = [
    re_path(r'^checkout/{course}/$'.format(course=COURSE_ID_PATTERN), Checkout.as_view(), name='checkout'),
]
