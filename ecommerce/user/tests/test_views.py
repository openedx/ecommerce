from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model


User = get_user_model()


class AutoAuthTests(TestCase):
    AUTO_AUTH_PATH = reverse('auto_auth')

    @override_settings(ENABLE_AUTO_AUTH=False)
    def test_setting_disabled(self):
        """When the ENABLE_AUTO_AUTH setting is False, the view should raise a 404."""
        response = self.client.get(self.AUTO_AUTH_PATH)
        self.assertEqual(response.status_code, 404)

    @override_settings(ENABLE_AUTO_AUTH=True)
    def test_setting_enabled(self):
        """
        When ENABLE_AUTO_AUTH is set to True, the view should create and authenticate
        a new User with superuser permissions.
        """
        original_user_count = User.objects.count()
        response = self.client.get(self.AUTO_AUTH_PATH)

        # Verify that a redirect has occured and that a new user has been created
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), original_user_count + 1)

        # Get the latest user
        user = User.objects.latest()

        # Verify that the user is logged in and that their username has the expected prefix
        self.assertEqual(self.client.session['_auth_user_id'], user.pk)
        self.assertTrue(user.username.startswith(settings.AUTO_AUTH_USERNAME_PREFIX))

        # Verify that the user has superuser permissions
        self.assertTrue(user.is_superuser)
