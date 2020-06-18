"""
Mixin for adding the enterprise discount in order line.
"""
import logging
from decimal import Decimal

from ecommerce.enterprise.utils import get_enterprise_customer_uuid_from_voucher
from ecommerce.extensions.payment.models import EnterpriseContractMetadata

logger = logging.getLogger(__name__)


class EnterpriseDiscountMixin:

    @staticmethod
    def _get_contract_metadata_for_manual_order(discount_percentage):
        """
        Return the EnterpriseContractMetadata object for manual
        order by inserting the given discount percentage.
        """
        return EnterpriseContractMetadata(
            discount_value=discount_percentage,
            discount_type=EnterpriseContractMetadata.PERCENTAGE
        )

    @staticmethod
    def _get_contract_metadata_for_order(order):
        """
        Return an EnterpriseContractMetadata object associated with an order.

        The contract metadata can live on the `attr` of a coupon product in the
        case of a coupon being redeemed (`mycoupon.attr.enterprise_contract_metadata`)

        -OR-

        The contract metadata can live on the conditional offer associated with
        the discount (that is associated with the order) in the case of an
        enterprise offer

        Args:
            order: An Order object

        Returns:
            A EnterpriseContractMetadata object if found else None.
        """
        for discount in order.discounts.all():
            # If a coupon is being redeemed
            if discount.voucher and get_enterprise_customer_uuid_from_voucher(discount.voucher):
                coupon = discount.voucher.coupon_vouchers.first().coupon
                contract_metadata = getattr(coupon.attr, 'enterprise_contract_metadata', None)
                if contract_metadata is not None:
                    logger.info("Using contract_metadata on coupon product for order [%s]", order.number)
                    return contract_metadata
            # If there is an enterprise offer
            if discount.offer and discount.offer.enterprise_contract_metadata:
                logger.info("Using contract_metadata on conditional offer for order [%s]", order.number)
                return discount.offer.enterprise_contract_metadata
        return None

    @staticmethod
    def _calculate_effective_discount_percentage(contract_metadata):
        """
        Returns the effective discount percentage on a contract.
        EnterpriseContractMetadata holds the value as a whole number,
        but on the orderline, we need to represent it as a decimaled
        percent (.23 instead of 23)

        Args:
            contract_metadata:  EnterpriseContractMetadata object

        Returns:
            A Decimal() object.
        """
        if contract_metadata.discount_type == EnterpriseContractMetadata.PERCENTAGE:
            return contract_metadata.discount_value * Decimal('.01')
        return contract_metadata.discount_value / (contract_metadata.discount_value + contract_metadata.amount_paid)

    @staticmethod
    def _get_enterprise_customer_cost_for_line(line_price, effective_discount_percentage):
        """
        Calculates the enterprise customer cost on a particular line item list price.

        Args:
            line_price: a Decimal object
            effective_discount_percentage: A Decimal() object. Is expected to
                be a decimaled percent (as in, .45 (representing 45 percent))

        Returns:
            A Decimal() object.
        """
        cost = line_price * (Decimal('1.00000') - effective_discount_percentage)

        # Round to 5 decimal places.
        return cost.quantize(Decimal('.00001'))

    def update_orderline_with_enterprise_discount_metadata(
            self,
            order,
            line,
            discount_percentage=None,
            is_manual_order=False
    ):
        """
        Updates an orderline with calculated discount metrics if applicable

        Args:
            order: An Order object
            line: A Line object
            discount_percentage: Decimal discounted percentage for manual order.
            is_manual_order: Boolean parameter tells this order is manual or not.

        Returns:
            Nothing

        Side effect:
            Saves a line object if effective_discount_percentage and enterprise_customer_cost can be calculated.
        """
        if is_manual_order:
            contract_metadata = self._get_contract_metadata_for_manual_order(discount_percentage=discount_percentage)
        else:
            contract_metadata = self._get_contract_metadata_for_order(order=order)

        if contract_metadata is None:
            return

        effective_discount_percentage = self._calculate_effective_discount_percentage(contract_metadata)
        effective_contract_discounted_price = self._get_enterprise_customer_cost_for_line(
            line.unit_price_excl_tax,
            effective_discount_percentage
        )

        logger.info(
            'Saving the effective_discount_percentage [%s], effective_contract_discounted_price [%s] for order [%s]',
            effective_discount_percentage,
            effective_contract_discounted_price,
            order.number
        )
        line.effective_contract_discount_percentage = effective_discount_percentage
        line.effective_contract_discounted_price = effective_contract_discounted_price
        line.save()
