from edx_rest_api_client.client import EdxRestApiClient
from e2e.constants import TEST_COURSE_KEY

from e2e.config import (
    ECOMMERCE_API_URL,
    ENROLLMENT_API_URL,
    OAUTH_ACCESS_TOKEN_URL,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET
)


class BaseApi(object):
    api_url_root = None
    append_slash = True

    def __init__(self):
        assert self.api_url_root
        access_token, __ = self.get_access_token()
        self._client = EdxRestApiClient(self.api_url_root, jwt=access_token, append_slash=self.append_slash)

    @staticmethod
    def get_access_token():
        """ Returns an access token and expiration date from the OAuth provider.

        Returns:
            (str, datetime)
        """
        return EdxRestApiClient.get_oauth_access_token(
            OAUTH_ACCESS_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, token_type='jwt'
        )


class EcommerceApi(BaseApi):
    api_url_root = ECOMMERCE_API_URL

    def create_refunds_for_course_run(self, username, course_run_id):
        """ Create refunds on the ecommmerce service for the given user and course run.

        Args:
            username (str)
            course_run_id(str)

        Returns:
            str[]: List of refund IDs.
        """
        return self._client.refunds.post({'username': username, 'course_id': course_run_id})

    def process_refund(self, refund_id, action):
        return self._client.refunds(refund_id).process.put({'action': action})


class EnrollmentApi(BaseApi):
    api_url_root = ENROLLMENT_API_URL
    append_slash = False

    def get_enrollment(self, username, course_run_id):
        """ Get enrollment details for the given user and course run.

        Args:
            username (str)
            course_run_id (str)
        """
        return self._client.enrollment('{},{}'.format(username, course_run_id)).get()
