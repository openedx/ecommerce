import requests
from requests.auth import AuthBase

from e2e.config import ACCESS_TOKEN, ENROLLMENT_API_URL


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
    def __init__(self, host=None, key=None):
        self.host = host or ENROLLMENT_API_URL
        self.key = key or ACCESS_TOKEN

    def get_enrollment_status(self, username, course_id):
        """
        Retrieve the enrollment status for given user in a given course.
        """
        url = '{host}/enrollment/{username},{course_id}'.format(host=self.host, username=username, course_id=course_id)
        return requests.get(url, auth=BearerAuth(self.key)).json()
