from django.core.urlresolvers import reverse
from django.test import LiveServerTestCase, override_settings
from oscar.core.loading import get_model
from oscar.test import factories
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.fulfillment.status import ORDER, LINE


Order = get_model('order', 'Order')
ShippingEventType = get_model('order', 'ShippingEventType')


class OrderListTests(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        cls.selenium = WebDriver()
        super(OrderListTests, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(OrderListTests, cls).tearDownClass()

    def setUp(self):
        super(OrderListTests, self).setUp()

        self.btn_selector = '[data-action=retry-fulfillment]'
        self.password = 'test'
        self.user = factories.UserFactory(password=self.password, is_superuser=True, is_staff=True)

        self.order = factories.create_order(user=self.user)
        self.order.status = ORDER.FULFILLMENT_ERROR
        self.order.save()
        self.order.lines.all().update(status=LINE.FULFILLMENT_CONFIGURATION_ERROR)

        ShippingEventType.objects.get_or_create(name=FulfillmentMixin.SHIPPING_EVENT_NAME)

    def _login(self):
        """ Log into the service and navigate to the order list view. """
        self.selenium.get(self.live_server_url + reverse('auto_auth'))
        self.selenium.get(self.live_server_url + reverse('dashboard:order-list'))

    def _retry_fulfillment(self):
        """ Click the retry fulfillment button and wait for the AJAX call to finish. """
        button = self.selenium.find_element_by_css_selector(self.btn_selector)
        self.assertEqual(unicode(self.order.number), button.get_attribute('data-order-number'))
        button.click()

        # Wait for the AJAX call to finish and display an alert
        WebDriverWait(self.selenium, 0.1).until(lambda d: d.find_element_by_css_selector('#messages .alert'))

    def assertAlertDisplayed(self, alert_class, text):
        """ Verifies that the most recent alert has the given class and message. """
        alert = self.selenium.find_elements_by_css_selector('#messages .alert')[-1]
        classes = alert.get_attribute('class').split(' ')
        self.assertIn(alert_class, classes, )
        self.assertEqual(alert.find_element_by_css_selector('.message').text, text)

    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    def test_retry_fulfillment(self):
        """
        The order list should display a "Retry Fulfillment" button beside orders in the Fulfillment Error state.
        Clicking the button should call the fulfillment API endpoint via AJAX. When successful, the order status
        should be updated, an alert displayed, and the button removed.
        """
        order_number = self.order.number

        self._login()
        self._retry_fulfillment()

        # Ensure the button is removed.
        self.assertRaises(NoSuchElementException, self.selenium.find_element_by_css_selector, self.btn_selector)

        # Ensure the status is updated.
        selector = 'tr[data-order-number="{}"] .order-status'.format(order_number)
        status = self.selenium.find_element_by_css_selector(selector)
        self.assertEqual(ORDER.COMPLETE, status.text)

        # Ensure an alert is displayed
        self.assertAlertDisplayed('alert-success', 'Order {} has been fulfilled.'.format(order_number))

    def test_fulfillment_failed(self):
        """ If fulfillment fails, an alert should be displayed, and the Retry Fulfillment button reactivated. """
        self._login()
        self._retry_fulfillment()

        # Ensure the status is unchanged.
        order_number = self.order.number
        selector = 'tr[data-order-number="{}"] .order-status'.format(order_number)
        status = self.selenium.find_element_by_css_selector(selector)
        self.assertEqual(ORDER.FULFILLMENT_ERROR, status.text)

        # Ensure the button is active
        button = self.selenium.find_element_by_css_selector(self.btn_selector)
        classes = button.get_attribute('class').split(' ')
        self.assertNotIn('disabled', classes, 'Button is disabled, but should have been re-enabled!')

        # Ensure an alert is displayed)
        self.assertAlertDisplayed('alert-error',
                                  'Failed to fulfill order {}: INTERNAL SERVER ERROR'.format(order_number))
