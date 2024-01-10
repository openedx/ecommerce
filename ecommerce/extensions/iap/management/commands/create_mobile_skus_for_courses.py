"""
This command calls the edx-platform API to create mobile skus for given course keys
"""
import json
import logging

import requests
from django.core.management import BaseCommand, CommandError

logger = logging.getLogger(__name__)

LOCAL_LMS_BASE_URL = 'http://edx.devstack.lms:18000'
LOCAL_ECOMMERCE_BASE_URL = 'http://edx.devstack.ecommerce:18130'
STAGE_LMS_BASE_URL = 'https://courses.stage.edx.org'
STAGE_ECOMMERCE_BASE_URL = 'https://ecommerce.stage.edx.org'
PROD_LMS_BASE_URL = 'https://courses.edx.org'
PROD_ECOMMERCE_BASE_URL = 'https://ecommerce.edx.org'
CREATE_MOBILE_SKUS_URL = '/api/iap/v1/create-mobile-skus/'
OAUTH_LOGIN_URL = '/oauth2/access_token/'
INPUT_FILE_NAME = 'course_keys_for_mobile_skus.txt'
OUTPUT_FILE_NAME = 'mobile_skus_response.txt'
NEW_MOBILE_SKUS_KEY = 'new_mobile_skus'
FAILED_COURSE_IDS_KEY = 'failed_course_ids'
FAILED_IOS_PRODUCTS = 'failed_ios_products'
MISSING_COURSE_RUNS_KEY = 'missing_course_runs'
LOCAL_ENVIRONMENT = 'local'
STAGE_ENVIRONMENT = 'stage'
PROD_ENVIRONMENT = 'prod'


class FailedAuthentication(Exception):
    pass


class Command(BaseCommand):
    """
    Call edx-platform API /api/iap/v1/create-mobile-skus/ to create mobile skus for given course keys.
    Format of response of the API /api/iap/v1/create-mobile-skus/ is as follows:
    {
        "new_mobile_skus": {
            "course-v1:course-key": [
                "mobile.android.sku",
                "mobile.ios.sku"
            ]
        },
        "failed_course_ids": [],
        "missing_course_runs": []
    }
    """

    help = 'Call edx-platform API to create mobile skus for given course keys.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            default=1000,
            help='Environment i.e. local/stage/prod')
        parser.add_argument(
            '--admin_username',
            type=str,
            default=1000,
            help='Username of admin user')
        parser.add_argument(
            '--admin_password',
            type=str,
            default=1000,
            help='Password of admin user')

    def handle(self, *args, **options):
        environment = options['environment']
        admin_username = options['admin_username']
        admin_password = options['admin_password']
        base_lms_url, base_ecommerce_url = self._get_base_urls(environment)
        create_skus_url = base_ecommerce_url + CREATE_MOBILE_SKUS_URL
        login_url = base_lms_url + OAUTH_LOGIN_URL

        headers = self._login_user_and_get_headers(admin_username, admin_password, login_url)
        complete_response = {
            NEW_MOBILE_SKUS_KEY: {},
            FAILED_COURSE_IDS_KEY: [],
            MISSING_COURSE_RUNS_KEY: [],
            FAILED_IOS_PRODUCTS: []
        }
        error_messages = []
        try:
            with open(INPUT_FILE_NAME, 'r+', encoding="utf-8") as input_file:
                course_keys = input_file.readlines()
                for course_key in course_keys:
                    course_key = course_key.strip()
                    payload = json.dumps({"courses": [course_key]})
                    response = requests.post(create_skus_url, data=payload, headers=headers)
                    if response.status_code == 401:
                        headers = self._login_user_and_get_headers(admin_username, admin_password, login_url)
                        # Retry request with fresh auth token
                        response = requests.post(create_skus_url, data=payload, headers=headers)

                    if response.status_code != 200:
                        error_message = 'Failed for course key {}. {}'.format(course_key, response.text)
                        error_messages.append(error_message)
                        continue

                    self._update_response_dictionary(response.json(), complete_response)
        except FileNotFoundError as error:
            raise CommandError('Input file with name {} does not exists.'.format(INPUT_FILE_NAME)) from error

        self._write_response_to_file(complete_response)

    def _login_user(self, username, password, login_url):
        """
        Login the user given the username and password.
        Return the JWT token if login successful.
        Raise exception if login failed.
        """
        payload = {
            'client_id': 'login-service-client-id',
            'grant_type': 'password',
            'username': username,
            'password': password,
            'token_type': 'jwt'
        }
        response = requests.post(login_url, payload)
        if not response.status_code == 200:
            raise FailedAuthentication

        jwt_token = response.json().get('access_token')
        return jwt_token

    def _login_user_and_get_headers(self, admin_username, admin_password, login_url):
        """ Login user and return auth headers """
        try:
            jwt_token = self._login_user(admin_username, admin_password, login_url)
        except FailedAuthentication as error:
            raise CommandError('Login failed') from error
        headers = self._get_headers(jwt_token)
        return headers

    def _get_headers(self, jwt_token):
        """ Return related headers for requests """
        return {
            'Authorization': 'JWT ' + jwt_token,
            'Content-Type': 'application/json',
        }

    def _get_base_urls(self, environment):
        """ Get base url for LMS and Ecommerce based on environment selected """
        base_lms_url = LOCAL_LMS_BASE_URL
        base_ecommerce_url = LOCAL_ECOMMERCE_BASE_URL
        if environment == STAGE_ENVIRONMENT:
            base_lms_url = STAGE_LMS_BASE_URL
            base_ecommerce_url = STAGE_ECOMMERCE_BASE_URL
        elif environment == PROD_ENVIRONMENT:
            base_lms_url = PROD_LMS_BASE_URL
            base_ecommerce_url = PROD_ECOMMERCE_BASE_URL

        return base_lms_url, base_ecommerce_url

    def _update_response_dictionary(self, new_response, complete_response):
        """ Update the complete_response dict with the contents of the new response """
        if new_response.get(NEW_MOBILE_SKUS_KEY):
            new_mobile_skus = new_response.get(NEW_MOBILE_SKUS_KEY)
            for key, value in new_mobile_skus.items():
                complete_response[NEW_MOBILE_SKUS_KEY][key] = value
        if new_response.get(FAILED_COURSE_IDS_KEY):
            complete_response[FAILED_COURSE_IDS_KEY] += new_response.get(FAILED_COURSE_IDS_KEY)
        if new_response.get(MISSING_COURSE_RUNS_KEY):
            complete_response[MISSING_COURSE_RUNS_KEY] += new_response.get(MISSING_COURSE_RUNS_KEY)
        if new_response.get(FAILED_IOS_PRODUCTS):
            complete_response[FAILED_IOS_PRODUCTS] += new_response.get(FAILED_IOS_PRODUCTS)

    def _write_response_to_file(self, response):
        with open(OUTPUT_FILE_NAME, 'w+', encoding="utf-8") as output_file:
            output_file.write(json.dumps(response))
