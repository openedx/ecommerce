from edx_rest_api_client.client import EdxRestApiClient
from requests.auth import AuthBase

from e2e.config import ENROLLMENT_API_URL, OAUTH_ACCESS_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET


def get_access_token():
    """ Returns an access token and expiration date from the OAuth provider.

    Returns:
        (str, datetime)
    """

    return EdxRestApiClient.get_oauth_access_token(
        OAUTH_ACCESS_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, token_type='jwt'
    )


class BearerAuth(AuthBase):
    """ Attaches Bearer Authentication to the given Request object. """

    def __init__(self, token):
        """ Instantiate the auth class. """
        self.token = token

    def __call__(self, r):
        """ Update the request headers. """
        r.headers['Authorization'] = 'Bearer {}'.format(self.token)
        return r


class EnrollmentApiClient(object):
    def __init__(self):
        access_token, __ = get_access_token()
        self.client = EdxRestApiClient(ENROLLMENT_API_URL, jwt=access_token, append_slash=False)

    def get_enrollment_status(self, username, course_id):
        """
        Retrieve the enrollment status for given user in a given course.
        """
        param = '{username},{course_id}'.format(username=username, course_id=course_id)
        return self.client.enrollment(param).get()
