from urllib.parse import urljoin

from edx_rest_api_client.client import OAuthAPIClient

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
        self._client = OAuthAPIClient(OAUTH_ACCESS_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET)

    def get_api_url(self, path):
        """
        Construct the full API URL using the api_url_root and path.

        Args:
            path (str): API endpoint path.
        """
        path = path.strip('/')
        if self.append_slash:
            path += '/'

        return urljoin(f"{self.api_url_root}/", path)  # type: ignore


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
        response = self._client.get(
            self.get_api_url("search/course_runs/facets/"),
            params={
                "selected_query_facets": "availability_current",
                "selected_facets": f"seat_types_exact:{seat_type}"
            }
        )
        response.raise_for_status()
        return response.json()['objects']['results']

    def get_course_run(self, course_run):
        """ Returns the details for a given course run.

        Args:
            course_run (str)

        Returns:
            dict
        """
        response = self._client.get(
            self.get_api_url(f"course_runs/{course_run}/"),
        )
        response.raise_for_status()
        return response.json()


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
        response = self._client.post(
            self.get_api_url("refunds/"),
            json={'username': username, 'course_id': course_run_id}
        )
        response.raise_for_status()
        return response.json()

    def process_refund(self, refund_id, action):
        response = self._client.put(
            self.get_api_url(f"refunds/{refund_id}/process/"),
            json={'action': action}
        )
        response.raise_for_status()
        return response.json()


class EnrollmentApi(BaseApi):
    api_url_root = ENROLLMENT_API_URL
    append_slash = False

    def get_enrollment(self, username, course_run_id):
        """ Get enrollment details for the given user and course run.

        Args:
            username (str)
            course_run_id (str)
        """
        response = self._client.get(
            self.get_api_url(f"enrollment/{username},{course_run_id}")
        )
        response.raise_for_status()
        return response.json()
