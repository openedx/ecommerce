

import uuid

from django.core.management import call_command
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
LOGGER_NAME = 'ecommerce.extensions.catalogue.management.commands.populate_enterprise_id_product_attribute'


class PopulateEnterpriseIDProductAttributeTests(TestCase, CouponMixin):
    """Tests for populate_enterprise_id_product_attribute management command."""

    def test_no_coupons_found(self):
        """Test that command logs no offer needs to be changed."""
        with LogCapture(LOGGER_NAME) as log:
            call_command('populate_enterprise_id_product_attribute')
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'Found 0 coupon products to update.'
                )
            )

    def test_populate_enterprise_id_product_attribute(self):
        """Test that command populates the enterprise id product attribute."""
        enterprise_id = str(uuid.uuid4())
        coupon = self.create_coupon(enterprise_customer=enterprise_id)
        expected = [
            (
                LOGGER_NAME,
                'INFO',
                'Found 1 coupon products to update.'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Processing batch from index 0 to 100'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Setting enterprise id product attribute for Product {} to value {}'.format(coupon.id, enterprise_id)
            ),
        ]

        with LogCapture(LOGGER_NAME) as log:
            call_command('populate_enterprise_id_product_attribute')
            log.check(*expected)

        coupon = Product.objects.get(id=coupon.id)
        assert coupon.attr.enterprise_customer_uuid == enterprise_id

    def test_populate_enterprise_id_product_attribute_in_batches(self):
        """Test that command populates enterprise id product attribute in batches."""
        coupon_count = 10
        coupon_ids = []
        enterprise_ids = []
        log_messages = []
        for idx in range(coupon_count):
            enterprise_id = str(uuid.uuid4())
            coupon = self.create_coupon(title='Test Coupon {}'.format(idx), enterprise_customer=enterprise_id)
            coupon_ids.append(coupon.id)
            enterprise_ids.append(enterprise_id)
            log_messages.append(
                (
                    LOGGER_NAME,
                    'INFO',
                    'Setting enterprise id product attribute for Product {} to value {}'.format(
                        coupon.id, enterprise_id)
                )
            )

        expected = [
            (
                LOGGER_NAME,
                'INFO',
                'Found {} coupon products to update.'.format(coupon_count)
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Processing batch from index 0 to 5'
            ),
        ]
        expected.extend(log_messages[:5])
        expected.append(
            (
                LOGGER_NAME,
                'INFO',
                'Processing batch from index 5 to 10'
            ),
        )
        expected.extend(log_messages[5:])

        with LogCapture(LOGGER_NAME) as log:
            call_command('populate_enterprise_id_product_attribute', limit=5)
            log.check(*expected)

        for idx in range(coupon_count):
            coupon = Product.objects.get(id=coupon_ids[idx])
            assert coupon.attr.enterprise_customer_uuid == enterprise_ids[idx]

    def test_populate_enterprise_id_product_attribute_with_exception(self):
        """Test that command with exception."""
        self.create_coupon(enterprise_customer=str(uuid.uuid4()))
        expected = [
            (
                LOGGER_NAME,
                'INFO',
                'Found 1 coupon products to update.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Command execution failed while executing batch -1,10\nNegative indexing is not supported.'
            )
        ]

        with LogCapture(LOGGER_NAME) as log:
            call_command('populate_enterprise_id_product_attribute', offset=-1, limit=10)
            log.check(*expected)
