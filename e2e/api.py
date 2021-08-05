from edx_rest_api_client.client import EdxRestApiClient

from e2e.config import (
    DISCOVERY_API_URL_ROOT,
    ECOMMERCE_API_URL,
    ENROLLMENT_API_URL,
    OAUTH_ACCESS_TOKEN_URL,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET
)


class BaseApi:
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


class DiscoveryApi(BaseApi):
    api_url_root = DISCOVERY_API_URL_ROOT

    def get_course_runs(self, seat_type):
        """ Returns a list of dicts containing data for current course runs with the given seat type.

        The search endpoint is used to find available course runs. Ultimately, the data returned comes from the
        course run detail endpoint called from get_course_run.

        Args:
            seat_type (str)

        Returns:
            list(dict)
        """
        results = self._client.search.course_runs.facets.get(
            selected_query_facets='availability_current', selected_facets=f'seat_types_exact:{seat_type}')
        return results['objects']['results']

    def get_course_run(self, course_run):
        """ Returns the details for a given course run.

        Args:
            course_run (str)

        Returns:
            dict
        """
        return self._client.course_runs(course_run).get()


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
        return self._client.enrollment(f'{username},{course_run_id}').get()
