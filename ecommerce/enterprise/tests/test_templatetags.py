

import httpretty
import mock
from django.conf import settings
from django.template import Context, Template
from oscar.core.loading import get_model

from ecommerce.core.tests import toggle_switch
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.enterprise.exceptions import EnterpriseDoesNotExist
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
TEST_ENTERPRISE_CUSTOMER_UUID = 'cf246b88-d5f6-4908-a522-fc307e0b0c59'


@httpretty.activate
class EnterpriseTemplateTagsTests(EnterpriseServiceMockMixin, CouponMixin, TestCase):
    def setUp(self):
        super(EnterpriseTemplateTagsTests, self).setUp()

        # Enable enterprise functionality
        toggle_switch(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, True)

    def test_enterprise_customer_for_voucher(self):
        """
        Verify that enterprise_customer_for_voucher assignment tag returns correct
        enterprise customer without any errors.
        """
        enterprise_customer_name = "Test Enterprise Customer"
        self.mock_access_token_response()
        self.mock_specific_enterprise_customer_api(TEST_ENTERPRISE_CUSTOMER_UUID, name=enterprise_customer_name)

        coupon = self.create_coupon(enterprise_customer=TEST_ENTERPRISE_CUSTOMER_UUID)
        voucher = coupon.attr.coupon_vouchers.vouchers.first()

        template = Template(
            "{% load enterprise %}"
            "{% enterprise_customer_for_voucher voucher as enterprise_customer %}"
            "{{ enterprise_customer.name }}"
        )
        result = template.render(Context({'voucher': voucher, 'request': self.request}))
        self.assertIn(enterprise_customer_name, result)

    @mock.patch('ecommerce.enterprise.templatetags.enterprise.utils.get_enterprise_customer_from_voucher')
    def test_enterprise_customer_for_voucher_when_enterprise_customer_does_not_exist(self, mock_utils):
        """
        Verify that enterprise_customer_for_voucher assignment tag returns None if
        enterprise customer does not exist.
        """
        mock_utils.side_effect = EnterpriseDoesNotExist()

        coupon = self.create_coupon(enterprise_customer='')
        voucher = coupon.attr.coupon_vouchers.vouchers.first()

        template = Template(
            "{% load enterprise %}"
            "{% enterprise_customer_for_voucher voucher as enterprise_customer %}"
            "{{ enterprise_customer.name }}"
        )
        result = template.render(Context({'voucher': voucher, 'request': self.request}))
        self.assertEqual(result, '')

    def test_enterprise_customer_for_voucher_when_context_missing_request(self):
        """
        Verify that enterprise_customer_for_voucher assignment tag returns None if
        enterprise customer does not exist.
        """

        coupon = self.create_coupon(enterprise_customer='')
        voucher = coupon.attr.coupon_vouchers.vouchers.first()

        template = Template(
            "{% load enterprise %}"
            "{% enterprise_customer_for_voucher voucher as enterprise_customer %}"
            "{{ enterprise_customer.name }}"
        )
        result = template.render(Context({'voucher': voucher}))
        self.assertEqual(result, '')

    def test_enterprise_customer_for_voucher_when_voucher_is_none(self):
        """
        Verify that enterprise_customer_for_voucher assignment tag returns None if
        provided voucher is None.
        """

        template = Template(
            "{% load enterprise %}"
            "{% enterprise_customer_for_voucher voucher as enterprise_customer %}"
            "{{ enterprise_customer.name }}"
        )
        result = template.render(Context({'voucher': None, 'request': self.request}))
        self.assertEqual(result, '')
