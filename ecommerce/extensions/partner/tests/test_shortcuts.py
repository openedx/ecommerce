from django.contrib.sites.models import Site
from django.test import TestCase, RequestFactory

from ecommerce.core.models import SiteConfiguration
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.tests.mixins import PartnerMixin


class ShortcutsTest(PartnerMixin, TestCase):
    def setUp(self):
        self.partner = self.create_partner('dummy')
        self.site, __ = Site.objects.get_or_create(domain='example.com')
        SiteConfiguration.objects.create(
            site=self.site,
            partner=self.partner,
            lms_url_root='https://courses.stage.edx.org',
            theme_scss_path='/css/path/',
            payment_processors='paypal'
        )

    def test_partner_for_site(self):
        request = RequestFactory().get('/')
        partner = get_partner_for_site(request)
        self.assertEqual('dummy', partner.short_code)
