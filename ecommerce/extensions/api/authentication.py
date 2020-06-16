""" Custom DRF authentication modules. """
from edx_rest_framework_extensions.auth.bearer.authentication import BearerAuthentication as BaseBearerAuthentication

from ecommerce.core.url_utils import get_oauth2_provider_url


class BearerAuthentication(BaseBearerAuthentication):
    """
    NOTE: This authentication class is deprecated, see ARCH-396.
    """

    def get_user_info_url(self):
        """ Returns the URL, hosted by the OAuth2 provider, from which user information can be pulled. """
        return '{base}/user_info/'.format(base=get_oauth2_provider_url())
