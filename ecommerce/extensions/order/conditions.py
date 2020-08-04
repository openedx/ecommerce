

import logging

import crum
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.extensions.offer.mixins import ConditionWithoutRangeMixin, SingleItemConsumptionConditionMixin

Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)


class ManualEnrollmentOrderDiscountCondition(
        ConditionWithoutRangeMixin,
        SingleItemConsumptionConditionMixin,
        Condition
):
    class Meta:
        app_label = 'order'
        proxy = True

    @property
    def name(self):
        return "Manual Course Enrollment Discount Condition"

    def is_satisfied(self, offer, basket):  # pylint: disable=unused-argument
        """
        If basket contain only 1 product and product is of type `seat` and seat is paid(not audit)
            return True
        else
            return False
        """
        if crum.get_current_request().META['PATH_INFO'] != reverse('api:v2:manual-course-enrollment-order-list'):
            self.log_error_message(
                'This condition is only applicable to manual course enrollement orders.',
                offer,
                basket
            )
            return False

        if offer.offer_type != ConditionalOffer.USER:
            self.log_error_message('Wrong offer type.', offer, basket)
            return False

        if not basket.lines.count() == 1:
            self.log_error_message('Basket must contain only 1 product.', offer, basket)
            return False

        if not basket.lines.first().product.is_seat_product:
            self.log_error_message('Basket contains non-seat type product.', offer, basket)
            return False

        if basket.lines.first().product.attr.certificate_type not in ('verified', 'professional', 'credit'):
            self.log_error_message('Basket contains non verified seat product.', offer, basket)
            return False

        return True

    def log_error_message(self, message, offer, basket):
        """
        Extract the available information from `offer` and `basket` and log the message.
        """
        prefix = '[Manual Order Creation Failure]'

        user = basket.owner.username
        basket_id = basket.id
        offer_id = offer.id
        # extract product ids to log
        product_ids = ', '.join([str(line.product.id) for line in basket.lines.all()])
        product_type = None
        product_cert = None

        line = basket.lines.first()
        if line:
            product_type = line.product.get_product_class().name
            product_cert = getattr(line.product.attr, 'certificate_type', None)

        logger.warning(
            '%s %s User: %s, Basket: %s, Offer: %s, Product: %s, ProductType: %s, ProductCert: %s',
            prefix,
            message,
            user, basket_id, offer_id, product_ids, product_type, product_cert
        )
