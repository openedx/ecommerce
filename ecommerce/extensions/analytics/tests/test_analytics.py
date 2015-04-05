# -*- coding: utf-8 -*-
"""Unit tests for the analytics app."""
from django.apps import apps
from django.test.utils import override_settings
from oscar.core.loading import get_model

from ecommerce.extensions.api.tests.test_integration import OrdersIntegrationTests


ProductRecord = get_model('analytics', 'ProductRecord')


class AnalyticsTests(OrdersIntegrationTests):
    """Test analytics behavior in controlled scenarios."""
    @override_settings(INSTALL_DEFAULT_ANALYTICS_RECEIVERS=False)
    def test_order_receiver_disabled(self):
        """Verify that Oscar's Analytics order receiver can be disabled."""
        self._initialize()
        self._create_and_verify_order(self.FREE_TRIAL_SKU)

        # Verify that no product records are kept
        self.assertFalse(ProductRecord.objects.all().exists())

    @override_settings(INSTALL_DEFAULT_ANALYTICS_RECEIVERS=True)
    def test_order_receiver_enabled(self):
        """Verify that Oscar's Analytics order receiver can be re-enabled."""
        self._initialize()
        self._create_and_verify_order(self.FREE_TRIAL_SKU)

        # Verify that product order counts are recorded
        product = ProductRecord.objects.get(product=self.free_trial)
        self.assertEqual(product.num_purchases, 1)

    def _initialize(self):
        """Execute initialization tasks for the analytics app."""
        # Django executes app config during startup for every management command.
        # As a result, the `ready` method is only called once, before Django knows
        # it's running tests. As a workaround, we explicitly call the `ready` method.
        apps.get_app_config('analytics').ready()
