"""
Tests for the checkout page.
"""
from django.core.urlresolvers import reverse
from django.test import TestCase

import mock
from ecommerce.credit import views


from ecommerce.tests.mixins import UserMixin


class CheckoutPageTest(UserMixin, TestCase):
    """Test for Checkout page"""
    def setUp(self):
        super(CheckoutPageTest, self).setUp()
        user = self.create_user(is_superuser=False)
        self.client.login(username=user.username, password=self.password)
        self.course_id = u'edx/Demo_Course/DemoX'

    def test_get_with_enabled_flag(self):
        """
        Test checkout page accessibility. Page will appear only if feature
        flag is enabled.
        """
        with mock.patch.object(views.waffle, 'flag_is_active') as mock_flag:
            mock_flag.return_value = True
            response = self.client.get(reverse('credit:checkout', args=[self.course_id]))

            self.assertEqual(response.status_code, 200)

    def test_get_with_disabled_flag(self):
        """
        Test checkout page accessibility. Page will return 404 if no flag is defined
        of it is disabled.
        """

        response = self.client.get(reverse('credit:checkout', args=[self.course_id]))

        self.assertEqual(response.status_code, 404)
