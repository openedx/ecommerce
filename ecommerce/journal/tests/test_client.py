"""
Tests functions in journal/client.py
"""
import json
import logging
import re
from urlparse import urljoin, urlsplit, urlunsplit

import responses
from edx_rest_api_client.auth import SuppliedJwtAuth
from edx_rest_api_client.client import EdxRestApiClient

from ecommerce.cache_utils.utils import TieredCache
from ecommerce.core.utils import get_cache_key
from ecommerce.journal.client import (
    fetch_journal_bundle,
    get_journals_service_client,
    post_journal_access,
    revoke_journal_access
)
from ecommerce.journal.constants import JOURNALS_API_PATH
from ecommerce.tests.testcases import TestCase

logger = logging.getLogger(__name__)


class JournalTestCase(TestCase):
    """
    Base test case for ecommerce journal tests.

    This class guarantees that tests have a Site and Partner available.
    """
    def setUp(self):
        super(JournalTestCase, self).setUp()
        self.site_configuration.journals_api_url = 'https://journal.example.com/api/v1/'
        self.journal_access_url = urljoin(self.site_configuration.journals_api_url, 'journalaccess/')

        split_url = urlsplit(self.site_configuration.discovery_api_url)
        self.journal_discovery_url = urlunsplit([
            split_url.scheme,
            split_url.netloc,
            JOURNALS_API_PATH,
            split_url.query,
            split_url.fragment
        ])

    def mock_access_token_response(self, status=200, **token_data):
        """ Mock the response from the OAuth provider's access token endpoint. """

        # Use a regex to account for the optional trailing slash
        url = '{root}/access_token/?'.format(root=self.site.siteconfiguration.oauth2_provider_url)
        url = re.compile(url)

        token = 'abc123'
        data = {
            'access_token': token,
            'expires_in': 3600,
        }
        data.update(token_data)
        body = json.dumps(data)
        responses.add(responses.POST, url, body=body, content_type='application/json', status=status)

        return token


class JournalClientTests(JournalTestCase):
    """ Test cases for the journal client.py """

    @responses.activate
    def test_get_journal_service_client(self):
        """ Test that 'get_journal_service_client' returns an EdxRestApiClient with the correct journal url
        and access token """
        token = self.mock_access_token_response()
        client = get_journals_service_client(self.site_configuration)
        client_store = client._store  # pylint: disable=protected-access
        client_auth = client_store['session'].auth

        self.assertIsInstance(client, EdxRestApiClient)
        self.assertEqual(client_store['base_url'], self.site_configuration.journals_api_url)
        self.assertIsInstance(client_auth, SuppliedJwtAuth)
        self.assertEqual(client_auth.token, token)

    @responses.activate
    def test_post_journal_access(self):
        """ Test 'post_journal_access' """
        self.mock_access_token_response()
        data = {
            'order_number': 'ORDER-64242',
            'user': 'lunalovegood',
            'journal': '4786e7be-2390-4332-a20e-e24895c38109'
        }
        responses.add(
            responses.POST,
            self.journal_access_url,
            status=200,
            body='{}',
            content_type='application/json'
        )

        post_journal_access(
            site_configuration=self.site_configuration,
            order_number=data['order_number'],
            username=data['user'],
            journal_uuid=data['journal']
        )

        # The first call (response.calls[0]) is to get post the access token
        # The second call (response.calls[1]) is the 'post_journal_access' call
        self.assertEqual(len(responses.calls), 2, "Incorrect number of API calls")
        request = responses.calls[1].request
        self.assertEqual(json.loads(request.body), data)
        self.assertEqual(request.method, responses.POST)
        response = responses.calls[1].response
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_revoke_journal_access(self):
        """ Test 'revoke_journal_access' """
        self.mock_access_token_response()
        data = {
            'order_number': 'ORDER-64242',
            'revoke_access': 'true'
        }
        responses.add(
            responses.POST,
            self.journal_access_url,
            status=200,
            body='{}',
            content_type='application/json'
        )

        revoke_journal_access(
            site_configuration=self.site_configuration,
            order_number=data['order_number']
        )

        # The first call (response.calls[0]) is to get post the access token
        # The second call (response.calls[1]) is the 'post_journal_access' call
        self.assertEqual(len(responses.calls), 2, "Incorrect number of API calls")
        request = responses.calls[1].request
        self.assertEqual(json.loads(request.body), data)
        self.assertEqual(request.method, responses.POST)
        response = responses.calls[1].response
        self.assertEqual(response.status_code, 200)

    @responses.activate
    def test_fetch_journal_bundle(self):
        """ Test 'fetch_journal_bundle'
        The first time it is called the journal discovery api should get hit
            and store the journal bundle in the cache
        The second time the api should not be called, the bundle should be retrieved from the cache
        """
        self.mock_access_token_response()
        test_bundle = {
            "uuid": "4786e7be-2390-4332-a20e-e24895c38109",
            "title": "Transfiguration Bundle",
            "partner": "edX",
            "journals": [
                {
                    "uuid": "a3db3f6e-f290-4eae-beea-873034c5a967",
                    "partner": "edx",
                    "organization": "edX",
                    "title": "Intermediate Transfiguration",
                    "price": "120.00",
                    "currency": "USD",
                    "sku": "88482D8",
                    "card_image_url": "http://localhost:18606/media/original_images/transfiguration.jpg",
                    "short_description": "Turning things into different things!",
                    "full_description": "",
                    "access_length": 365,
                    "status": "active",
                    "slug": "intermediate-transfiguration-about-page"
                }
            ],
            "courses": [
                {
                    "key": "HogwartsX+TR301",
                    "uuid": "6d7c2805-ec9c-4961-8b0d-c8d608cc948e",
                    "title": "Transfiguration 301",
                    "course_runs": [
                        {
                            "key": "course-v1:HogwartsX+TR301+TR301_2014",
                            "uuid": "ddaa84ce-e99c-4e3d-a3ca-7d5b4978b43b",
                            "title": "Transfiguration 301",
                            "image": 'fake_image_url',
                            "short_description": 'fake_description',
                            "marketing_url": 'fake_marketing_url',
                            "seats": [],
                            "start": "2030-01-01T00:00:00Z",
                            "end": "2040-01-01T00:00:00Z",
                            "enrollment_start": "2020-01-01T00:00:00Z",
                            "enrollment_end": "2040-01-01T00:00:00Z",
                            "pacing_type": "instructor_paced",
                            "type": "fake_course_type",
                            "status": "published"
                        }
                    ],
                    "entitlements": [],
                    "owners": [
                        {
                            "uuid": "becfbab0-c78d-42f1-b44e-c92abb99011a",
                            "key": "HogwartsX",
                            "name": ""
                        }
                    ],
                    "image": "fake_image_url",
                    "short_description": "fake_description"
                }
            ],
            "applicable_seat_types": [
                "verified"
            ]
        }

        journal_bundle_uuid = test_bundle['uuid']
        test_url = urljoin(self.journal_discovery_url, 'journal_bundles/{}/'.format(journal_bundle_uuid))

        responses.add(
            responses.GET,
            test_url,
            json=test_bundle,
            status=200
        )

        # First call, should hit journal discovery api and store in cache
        journal_bundle_response = fetch_journal_bundle(
            site=self.site,
            journal_bundle_uuid=journal_bundle_uuid
        )

        # The first call (response.calls[0]) is to get post the access token
        # The second call (response.calls[1]) is the 'fetch_journal_bundle' call
        self.assertEqual(len(responses.calls), 2, "Incorrect number of API calls")
        self.assertEqual(journal_bundle_response, test_bundle)

        # check that the journal bundle was stored in the cache
        cache_key = get_cache_key(
            site_domain=self.site.domain,
            resource='journal_bundle',
            journal_bundle_uuid=journal_bundle_uuid
        )
        journal_bundle_cached_response = TieredCache.get_cached_response(cache_key)
        self.assertTrue(journal_bundle_cached_response is not None)
        self.assertEqual(journal_bundle_cached_response.value, test_bundle)

        # Call 'fetch_journal_bundle' again, the api should not get hit again and response should be the same
        journal_bundle_response = fetch_journal_bundle(
            site=self.site,
            journal_bundle_uuid=journal_bundle_uuid
        )

        self.assertEqual(len(responses.calls), 2, "Should have hit cache, not called API")
        self.assertEqual(journal_bundle_response, test_bundle)
