from __future__ import unicode_literals

import json

import ddt
import mock
from django.urls import reverse

from ecommerce.tests.testcases import TestCase


@ddt.ddt
class AssignmentEmailTests(TestCase):
    """ Tests for AssignmentEmail API view. """
    path = reverse('api:v2:assignmentemail')

    def setUp(self):
        super(AssignmentEmailTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.data = {
            'template': ('Template message with '
                         '{user_email} {code}'
                         ' {enrollment_url} {code_usage_count} {code_expiration_date}'),
            'template_tokens': [
                {
                    'user_email': 'johndoe@unknown.com',
                    'code': 'GIL7RUEOU7VHBH7Q',
                    'enrollment_url': 'http://tempurl.url/enroll',
                    'code_usage_count': '3',
                    'code_expiration_date': '2012-04-23T18:25:43.511Z'
                },
                {
                    'user_email': 'janedoe@unknown.com',
                    'enrollment_url': '',
                    'code_usage_count': '3',
                    'code_expiration_date': '2012-04-23T18:25:43.511Z'
                },
            ]
        }

    def test_authentication_required(self):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 401)

    @mock.patch('ecommerce_worker.sailthru.v1.tasks.send_code_assignment_email.delay')
    @ddt.data(
        (
            # A valid request.
            {
                'template': ('Template message with '
                             '{user_email} {code}'
                             ' {enrollment_url} {code_usage_count} {code_expiration_date}'),
                'template_tokens': [
                    {
                        'user_email': 'johndoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7Q',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                    {
                        'user_email': 'janedoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7P',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                ]
            },
            {u'status': [{u'code': u'GIL7RUEOU7VHBH7Q',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Dispatched',
                          u'template_key_error': None,
                          u'user_email': u'johndoe@unknown.com'},
                         {u'code': u'GIL7RUEOU7VHBH7P',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Dispatched',
                          u'template_key_error': None,
                          u'user_email': u'janedoe@unknown.com'}]},
            200,
            None,
            2
        ),
        (
            # A bad request due to a missing field
            {
                'template': ('Template message with '
                             '{user_email} {code}'
                             ' {enrollment_url} {code_usage_count} {code_expiration_date}'),
                'template_tokens': [
                    {
                        'user_email': 'johndoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7Q',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                    {
                        'user_email': 'janedoe@unknown.com',
                        'enrollment_url': '',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                ]
            },
            {u'status': [{u'code': u'GIL7RUEOU7VHBH7Q',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Dispatched',
                          u'template_key_error': None,
                          u'user_email': u'johndoe@unknown.com'},
                         {u'code': None,
                          u'missing_keys': [u'code'],
                          u'missing_values': [u'enrollment_url'],
                          u'status': u'Failed',
                          u'template_key_error': None,
                          u'user_email': None}]},
            200,
            None,
            1
        ),
        (
            # Email task exception issue
            {
                'template': ('Template message with '
                             '{user_email} {code}'
                             ' {enrollment_url} {code_usage_count} {code_expiration_date}'),
                'template_tokens': [
                    {
                        'user_email': 'johndoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7Q',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                    {
                        'user_email': 'janedoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7P',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                ]
            },
            {u'status': [{u'code': u'GIL7RUEOU7VHBH7Q',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Failed',
                          u'template_key_error': None,
                          u'user_email': u'johndoe@unknown.com'},
                         {u'code': u'GIL7RUEOU7VHBH7P',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Failed',
                          u'template_key_error': None,
                          u'user_email': u'janedoe@unknown.com'}]},
            200,
            Exception(),
            2
        ),
        (
            # Missing template
            {
                'template_tokens': [
                    {
                        'user_email': 'johndoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7Q',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                    {
                        'user_email': 'janedoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7P',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                ]
            },
            {u'error': u'Required parameters are missing'},
            400,
            None,
            0
        ),
        (
            # Missing template key.
            {
                'template': ('Template message with '
                             '{user_email} {code}'
                             ' {enrollment_ur} {code_usage_count} {code_expiration_date}'),
                'template_tokens': [
                    {
                        'user_email': 'johndoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7Q',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                    {
                        'user_email': 'janedoe@unknown.com',
                        'code': 'GIL7RUEOU7VHBH7P',
                        'enrollment_url': 'http://tempurl.url/enroll',
                        'code_usage_count': '3',
                        'code_expiration_date': '2012-04-23T18:25:43.511Z'
                    },
                ]
            },
            {u'status': [{u'code': u'GIL7RUEOU7VHBH7Q',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Failed',
                          u'template_key_error': u"u'enrollment_ur'",
                          u'user_email': u'johndoe@unknown.com'},
                         {u'code': u'GIL7RUEOU7VHBH7P',
                          u'missing_keys': [],
                          u'missing_values': [],
                          u'status': u'Failed',
                          u'template_key_error': u"u'enrollment_ur'",
                          u'user_email': u'janedoe@unknown.com'}]},
            200,
            None,
            0
        )
    )
    @ddt.unpack
    def test_email_task_success(
            self,
            post_data,
            response_data,
            status_code,
            mock_side_effect,
            count,
            mock_send_code_assignment_email,
    ):
        """ Verify the endpoint schedules async task to send email """
        mock_send_code_assignment_email.side_effect = mock_side_effect
        response = self.client.post(self.path, data=json.dumps(post_data), content_type='application/json')
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response_data, json.loads(response.content))
        self.assertEqual(mock_send_code_assignment_email.call_count, count)
