from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase

from ecommerce.tests.mixins import UserMixin


class CourseMigrationViewTests(UserMixin, TestCase):
    path = reverse('migrate_course')

    def test_superuser_required(self):
        """ Verify the view is only accessible to superusers. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 404)

        user = self.create_user(is_superuser=False)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 404)

        user = self.create_user(is_superuser=True)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path + '?course_ids=foo')
        self.assertEqual(response.status_code, 200)

    def test_course_ids_required(self):
        """ The view should return HTTP status 400 if no course IDs are provided. """
        user = self.create_user(is_superuser=True)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)

        response = self.client.get(self.path + '?course_ids=')
        self.assertEqual(response.status_code, 400)

        response = self.client.get(self.path + '?course_ids=foo')
        self.assertEqual(response.status_code, 200)


class CourseListViewTests(UserMixin, TestCase):
    path = reverse('courses_list')

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_staff_user_required(self):
        """ Verify the view is only accessible to staff users. """
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 404)

        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
