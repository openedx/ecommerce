import mock

from ecommerce.courses.constants import CertificateType
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.executive_education_2u.utils import (
    get_executive_education_2u_product,
    get_learner_portal_url
)
from ecommerce.tests.testcases import TestCase


class UtilsTests(TestCase):
    def setUp(self):
        super().setUp()

    def test_get_executive_education_2u_product(self):
        exec_ed_2u_product = create_or_update_course_entitlement(
            CertificateType.PAID_EXECUTIVE_EDUCATION, 100, self.partner, 'product', 'Entitlement Product'
        )
        non_exec_ed_2u_product = create_or_update_course_entitlement(
            'verified', 100, self.partner, 'product', 'Entitlement Product'
        )

        exec_ed_2u_product_sku = exec_ed_2u_product.stockrecords.first().partner_sku
        non_exec_ed_2u_product_sku = non_exec_ed_2u_product.stockrecords.first().partner_sku

        self.assertEqual(
            get_executive_education_2u_product(self.partner, sku=exec_ed_2u_product_sku),
            exec_ed_2u_product
        )
        self.assertEqual(
            get_executive_education_2u_product(self.partner, sku=non_exec_ed_2u_product_sku),
            None
        )

    @mock.patch('ecommerce.extensions.executive_education_2u.utils.get_enterprise_customer')
    def test_get_learner_portal_url(self, mock_get_enterprise_customer):
        slug = 'sluggy'
        hostname = 'mock-hostname'
        mock_get_enterprise_customer.return_value = {
            'slug': slug
        }
        mock_request = mock.MagicMock(scheme='http', site=self.site)

        with self.settings(ENTERPRISE_LEARNER_PORTAL_HOSTNAME=hostname):
            expected_url = '{scheme}://{hostname}/{slug}'.format(
                scheme=mock_request.scheme,
                hostname=hostname,
                slug=slug,
            )
            self.assertEqual(get_learner_portal_url(mock_request), expected_url)
