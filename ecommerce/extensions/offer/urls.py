from django.conf.urls import url

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.extensions.offer.views import EmailConfirmationRequiredView

urlpatterns = [
    url(
        fr'^email_confirmation/$',
        EmailConfirmationRequiredView.as_view(),
        name='email_confirmation',
    ),
]
