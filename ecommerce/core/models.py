from django.contrib.auth.models import AbstractUser
from jsonfield.fields import JSONField
from django.db import models
from django.utils.translation import ugettext_lazy as _


class User(AbstractUser):
    """Custom user model for use with OIDC."""

    full_name = models.CharField(_('Full Name'), max_length=255, blank=True, null=True)

    @property
    def access_token(self):
        try:
            return self.social_auth.first().extra_data[u'access_token']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return None

    tracking_context = JSONField(blank=True, null=True)

    class Meta(object):
        get_latest_by = 'date_joined'
        db_table = 'ecommerce_user'

    def get_full_name(self):
        return self.full_name or super(User, self).get_full_name()
