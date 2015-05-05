from bok_choy.web_app_test import WebAppTest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from acceptance_tests.config import VERIFIED_COURSE_ID, HTTPS_RECEIPT_PAGE

from acceptance_tests.mixins import LoginMixin, EnrollmentApiMixin, EcommerceApiMixin, LmsUserMixin
from acceptance_tests.pages import LMSCourseModePage


class VerifiedCertificatePaymentTests(EcommerceApiMixin, EnrollmentApiMixin, LmsUserMixin, LoginMixin, WebAppTest):
    def setUp(self):
        super(VerifiedCertificatePaymentTests, self).setUp()
        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()

    def test_payment(self):
        self.login_with_lms(self.email, self.password)
        course_modes_page = LMSCourseModePage(self.browser, self.course_id)
        course_modes_page.visit()

        course_modes_page.purchase_verified()

        if not HTTPS_RECEIPT_PAGE:
            self.browser.switch_to_alert().accept()

        # Wait for the payment processor response to be processed, and the receipt page updated.
        WebDriverWait(self.browser, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'content-main')))

        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

        # Verify we reach the receipt page.
        self.assertIn('receipt', self.browser.title.lower())

        cells = self.browser.find_elements_by_css_selector('table.report-receipt tbody td')
        self.assertGreater(len(cells), 0)
        order = self.ecommerce_api_client.get_orders()[0]
        line = order['lines'][0]
        expected = [
            order['number'],
            line['description'],
            order['date_placed'].strftime('%Y-%m-%dT%H:%M:%S'),
            '{amount} ({currency})'.format(amount=line['line_price_excl_tax'], currency=order['currency'])
        ]
        actual = [cell.text for cell in cells]
        self.assertListEqual(actual, expected)
