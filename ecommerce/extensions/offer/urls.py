

from django.conf.urls import url

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.extensions.offer.views import EmailConfirmationRequiredView

urlpatterns = [
    url(
        r'^email_confirmation/$'.format(course_id=COURSE_ID_PATTERN),
        EmailConfirmationRequiredView.as_view(),
        name='email_confirmation',
    ),
]
