from django.test import TestCase
from django.urls import reverse

from ecommerce.tests.mixins import UserMixin


class ManagementViewTests(UserMixin, TestCase):
    path = reverse('management:index')

    def setUp(self):
        super(ManagementViewTests, self).setUp()
        self.user = self.create_user(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=self.password)

    def test_login_required(self):
        """ Verify the view requires login. """
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)

    def test_superuser_required(self):
        """ Verify the view is not accessible to non-superusers. """
        self.client.logout()
        user = self.create_user()
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)
