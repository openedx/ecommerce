from __future__ import unicode_literals

import json

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.reverse import reverse
from waffle.models import Flag


class FeaturesList(TestCase):
    @override_settings(TOP_LEVEL_COOKIE_DOMAIN='example.com')
    def test_get(self):
        """ Verify the view returns a list of features, and writes the data to a cookie. """
        flag = Flag.objects.create(name='test-flag', everyone=True)
        response = self.client.get(reverse('features:list'))
        self.assertEqual(response.status_code, 200)

        json_response = json.loads(response.content)
        expected = {'flags': {
            flag.name: True
        }}
        self.assertEqual(json_response, expected)

        cookie = self.client.cookies['features']
        self.assertEqual(json.loads(cookie.value), expected)
        self.assertEqual(cookie['domain'], settings.TOP_LEVEL_COOKIE_DOMAIN)
