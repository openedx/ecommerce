from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model for use with OIDC."""
    @property
    def access_token(self):
        try:
            return self.social_auth.first().extra_data[u'access_token']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return None

    class Meta(object):
        get_latest_by = 'date_joined'
        db_table = 'ecommerce_user'
