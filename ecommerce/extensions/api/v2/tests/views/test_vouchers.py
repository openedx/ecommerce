from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse
from oscar.test.factories import ConditionalOfferFactory, VoucherFactory

from ecommerce.tests.testcases import TestCase


class VoucherViewSetTests(TestCase):
    """ Tests for the VoucherViewSet view set. """
    coupon_code = 'COUPONCODE'
    path = reverse('api:v2:vouchers-list')

    def setUp(self):
        super(VoucherViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        voucher1 = VoucherFactory()
        voucher1.offers.add(ConditionalOfferFactory())
        self.voucher = VoucherFactory(code=self.coupon_code)
        self.voucher.offers.add(ConditionalOfferFactory(name='test2'))

    def test_voucher_listing(self):
        """ Verify the endpoint lists out all vouchers. """
        response = self.client.get(self.path)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['count'], 2)
        self.assertEqual(response_data['results'][1]['code'], self.coupon_code)

    def test_voucher_filtering(self):
        """ Verify the endpoint filters by code. """
        filter_path = '{}?code={}'.format(self.path, self.coupon_code)
        response = self.client.get(filter_path)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['count'], 1)
        self.assertEqual(response_data['results'][0]['code'], self.coupon_code)
