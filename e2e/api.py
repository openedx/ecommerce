

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

    def get_course_run(self, seat_type):
        """ Returns a dict containing data for a current course run with the given seat type.

        The search endpoint is used to find an available course run. Ultimately, the data returned comes from the
        course run detail endpoint.

        Args:
            seat_type (str)

        Returns:
            dict
        """
        results = self._client.search.course_runs.facets.get(
            selected_query_facets='availability_current', selected_facets='seat_types_exact:{}'.format(seat_type))
        results = results['objects']['results']
        # TODO Verify the course run exists on LMS and Otto. Some course runs are only present on Drupal.
        # TODO Cache the result so we don't waste resources doing this work again. The search endpoint order is stable.
        return self._client.course_runs(results[0]['key']).get()


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
