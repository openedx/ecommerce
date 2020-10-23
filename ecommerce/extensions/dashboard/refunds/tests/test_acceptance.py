

import os
from unittest import SkipTest, skip

import ddt
import pytest
from bok_choy.browser import browser
from django.urls import reverse
from oscar.core.loading import get_model
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait

from ecommerce.extensions.refund.status import REFUND
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import LiveServerTestCase

Refund = get_model('refund', 'Refund')

ALL_REFUND_STATUSES = (
    REFUND.OPEN, REFUND.PAYMENT_REFUND_ERROR, REFUND.PAYMENT_REFUNDED, REFUND.REVOCATION_ERROR, REFUND.COMPLETE,
    REFUND.DENIED
)


@ddt.ddt
@pytest.mark.acceptance
class RefundAcceptanceTestMixin(RefundTestMixin):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('DISABLE_ACCEPTANCE_TESTS') == 'True':
            raise SkipTest

        cls.selenium = browser()
        cls.selenium.set_page_load_timeout(30)
        super(RefundAcceptanceTestMixin, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(RefundAcceptanceTestMixin, cls).tearDownClass()

    def setUp(self):
        super(RefundAcceptanceTestMixin, self).setUp()

        self.refund = self.create_refund()

        self.approve_button_selector = '[data-refund-id="{}"] [data-decision="approve"]'.format(self.refund.id)
        self.deny_button_selector = '[data-refund-id="{}"] [data-decision="deny"]'.format(self.refund.id)

        self.password = 'test'
        self.user = UserFactory(password=self.password, is_superuser=True, is_staff=True)

    def _login(self):
        """Log into the service and navigate to the refund list view."""
        self.selenium.get(self.live_server_url + reverse('auto_auth'))
        self.selenium.get(self.live_server_url + self.path)

    def _decide(self, approve, confirm=True):
        """Click the Approve or Deny button and wait for the AJAX call to finish."""
        selector = self.approve_button_selector if approve else self.deny_button_selector
        button = self.selenium.find_element_by_css_selector(selector)
        button.click()

        # Wait for the modal to display, demanding confirmation
        WebDriverWait(self.selenium, 10).until(
            lambda d: d.find_element_by_css_selector('#refundActionModal').is_displayed()
        )
        if confirm:
            # click confirm
            self.selenium.find_element_by_css_selector('#refundActionModal .btn-primary').click()
            # Wait for the AJAX call to finish and display an alert
            WebDriverWait(self.selenium, 10).until(lambda d: d.find_element_by_css_selector('#messages .alert'))
        else:
            self.selenium.find_element_by_css_selector('#refundActionModal .btn-default').click()

        # Wait for the modal to be gone
        WebDriverWait(self.selenium, 10).until(
            lambda d: not d.find_element_by_css_selector('#refundActionModal').is_displayed()
        )

    def assert_alert_displayed(self, alert_class, text):
        """Verifies that the most recent alert has the given class and message."""
        alert = self.selenium.find_elements_by_css_selector('#messages .alert')[-1]
        classes = alert.get_attribute('class').split(' ')
        self.assertIn(alert_class, classes)
        self.assertEqual(alert.find_element_by_css_selector('.message').text, text)

    @skip("Requires refund processing endpoint.  Move to e2e and re-enable under ticket XCOM-342.")
    @ddt.data(True, False)
    def test_processing_success(self, approve):
        """
        Verify behavior when refund processing succeeds.

        The refund list should display "Approve" and "Deny buttons next to each refund. Clicking either button
        should call the refund processing API endpoint via AJAX. When a refund is processed successfully, the refund's
        status should be updated, an alert should displayed, and both buttons should be removed.
        """
        self._login()
        self._decide(approve)

        # Verify that both buttons have been removed from the DOM.
        self.assertRaises(
            NoSuchElementException,
            self.selenium.find_element_by_css_selector,
            self.approve_button_selector
        )
        self.assertRaises(
            NoSuchElementException,
            self.selenium.find_element_by_css_selector,
            self.deny_button_selector
        )

        # Verify that the refund's status is updated.
        selector = 'tr[data-refund-id="{}"] .refund-status'.format(self.refund.id)
        status = self.selenium.find_element_by_css_selector(selector)
        if approve:
            self.assertEqual(REFUND.COMPLETE, status.text)
        else:
            self.assertEqual(REFUND.DENIED, status.text)

        # Verify that an alert is displayed.
        self.assert_alert_displayed('alert-success', 'Refund {} has been processed.'.format(self.refund.id))

    @skip("This test is flaky in Travis.  Move to e2e and re-enable under ticket XCOM-342.")
    @ddt.data(True, False)
    def test_processing_failure(self, approve):
        """
        Verify behavior when refund processing fails.

        The refund list should display "Approve" and "Deny" buttons next to
        each refund. Clicking either button should trigger a confirmation
        modal.

        When the user confirms at the modal, call the refund processing API
        endpoint via AJAX. When refund processing fails, the refund's status
        should be updated, an alert should displayed, and both buttons should
        be reactivated.
        """
        self._login()

        # Before clicking any buttons, delete the refund from the system to cause a processing error.
        refund_id = self.refund.id
        Refund.objects.get(id=refund_id).delete()

        self._decide(approve)

        # Verify that both buttons are active.
        for button_selector in [self.approve_button_selector, self.deny_button_selector]:
            button = self.selenium.find_element_by_css_selector(button_selector)
            classes = button.get_attribute('class').split(' ')
            self.assertNotIn(
                'disabled',
                classes,
                'Refund processing button is disabled, but should have been re-enabled!'
            )

        # Verify that the refund's status is updated.
        selector = 'tr[data-refund-id="{}"] .refund-status'.format(refund_id)
        status = self.selenium.find_element_by_css_selector(selector)
        self.assertEqual('Error', status.text)

        # Verify that an alert is displayed.
        self.assert_alert_displayed(
            'alert-error',
            'Failed to process refund #{refund_id}: NOT FOUND. '
            'Please try again, or contact the E-Commerce Development Team.'.format(refund_id=refund_id)
        )

    @ddt.data(True, False)
    def test_cancel_action(self, approve):
        """
        Verify that the UI returns to its previous state unchanged, when a user
        clicks one of the refund action buttons, but then cancels the operation
        at the confirmation modal.
        """
        self._login()
        self._decide(approve, False)

        # Verify that both buttons are active.
        for button_selector in [self.approve_button_selector, self.deny_button_selector]:
            button = self.selenium.find_element_by_css_selector(button_selector)
            classes = button.get_attribute('class').split(' ')
            self.assertNotIn(
                'disabled',
                classes,
                'Refund processing button is disabled, but should have been re-enabled!'
            )

    @ddt.data(*ALL_REFUND_STATUSES)
    def test_button_configurations(self, status):
        """
        Verify correct button configurations for different refund statuses.
        """
        self.refund.status = status
        self.refund.save()

        self._login()

        if self.refund.can_approve:
            self.selenium.find_element_by_css_selector(self.approve_button_selector)
        else:
            self.assertRaises(
                NoSuchElementException,
                self.selenium.find_element_by_css_selector,
                self.approve_button_selector
            )

        if self.refund.can_deny:
            self.selenium.find_element_by_css_selector(self.deny_button_selector)
        else:
            self.assertRaises(
                NoSuchElementException,
                self.selenium.find_element_by_css_selector,
                self.deny_button_selector
            )


class RefundListViewTests(RefundAcceptanceTestMixin, LiveServerTestCase):
    """Acceptance tests of the refund list view."""

    def setUp(self):
        super(RefundListViewTests, self).setUp()
        self.path = reverse('dashboard:refunds-list')


class RefundDetailViewTests(RefundAcceptanceTestMixin, LiveServerTestCase):
    """Acceptance tests of the refund detail view."""

    def setUp(self):
        super(RefundDetailViewTests, self).setUp()
        self.path = reverse('dashboard:refunds-detail', args=[self.refund.id])
