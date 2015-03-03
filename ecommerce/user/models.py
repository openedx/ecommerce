from django.db import models
from django.utils.translation import ugettext_lazy as _

from oscar.apps.customer.abstract_models import AbstractUser


class User(AbstractUser):
    """Custom user model for use with OIDC."""
    # The Enrollment API expects a username, which it uses when performing enrollments
    username = models.CharField(_('username'), max_length=30, unique=True)

    @property
    def access_token(self):
        try:
            return self.social_auth.first().extra_data[u'access_token']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return None

    class Meta(object):
        get_latest_by = 'date_joined'
        db_table = 'ecommerce_user'
