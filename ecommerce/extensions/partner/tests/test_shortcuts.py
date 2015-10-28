from django.test import TestCase
from mock import Mock

from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.tests.mixins import SiteMixin


class ShortcutsTest(SiteMixin, TestCase):
    def test_get_partner_for_site(self):
        """ Verify the function returns the Partner associated with the request's Site. """
        request = Mock()
        request.site = self.site
        self.assertEqual(get_partner_for_site(request), self.partner)
