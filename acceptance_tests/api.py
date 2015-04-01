import datetime

import requests
from requests.auth import AuthBase

from acceptance_tests.config import (ENROLLMENT_API_URL, ENROLLMENT_API_TOKEN, ECOMMERCE_API_SERVER_URL,
                                     ECOMMERCE_API_TOKEN)


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
        self.key = key or ENROLLMENT_API_TOKEN

    def get_enrollment_status(self, username, course_id):
        """
        Retrieve the enrollment status for given user in a given course.
        """
        url = '{host}/enrollment/{username},{course_id}'.format(host=self.host, username=username, course_id=course_id)
        return requests.get(url, auth=BearerAuth(self.key)).json()


class EcommerceApiClient(object):
    def __init__(self, host=None, key=None):
        self.host = host or '{}/api/v1'.format(ECOMMERCE_API_SERVER_URL)
        self.key = key or ECOMMERCE_API_TOKEN

    def orders(self):
        """ Retrieve the orders for the user linked to the authenticated user. """
        url = '{}/orders/'.format(self.host)
        response = requests.get(url, auth=BearerAuth(self.key))
        data = response.json()

        status_code = response.status_code
        if status_code != 200:
            raise Exception('Invalid E-Commerce API response: [{}] - [{}]'.format(status_code, data))

        orders = data['results']

        for order in orders:
            order['date_placed'] = datetime.datetime.strptime(order['date_placed'], "%Y-%m-%dT%H:%M:%S.%fZ")

        return orders
