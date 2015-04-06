"""Fulfillment Modules with specific fulfillment logic per Product Type, or a Combination of Types

Fulfillment Modules are designed to allow specific fulfillment logic based on the type (or types) of products
in an Order.
"""
# pylint: disable=abstract-method
import json
import logging

import requests
from requests.exceptions import ConnectionError, Timeout
from django.conf import settings
from rest_framework import status
from oscar.apps.catalogue.models import ProductAttributeValue

from ecommerce.extensions.fulfillment.status import LINE


logger = logging.getLogger(__name__)


class FulfillmentModule(object):
    """ Base FulfillmentModule class for containing Product specific fulfillment logic.

    All modules should extend the FulfillmentModule and adhere to the defined contract.

    """

    def get_supported_lines(self, order, lines):
        """ Return a list of supported lines in the order

        Each Fulfillment Module is capable of fulfillment certain products. This function allows a preliminary
        check of which lines could be supported by this Fulfillment Module.

         By evaluating the order and the lines, this will return a list of all the lines in the order that
         can be fulfilled by this module.

        Args:
            order (Order): The Order associated with the lines to be fulfilled
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of lines, unmodified.

        """
        raise NotImplementedError("Line support method not implemented!")

    def fulfill_product(self, order, lines):
        """ Fulfills the specified lines in the order.

        Iterates over the given lines and fulfills the associated products. Will report success if the product can
        be fulfilled, but may fail if the module cannot support fulfillment of the specified product, or there is
        an error with the services required to fulfill the current product.

        Args:
            order (Order): The Order associated with the lines to be fulfilled
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.

        """
        raise NotImplementedError("Fulfillment method not implemented!")

    def revoke_product(self, order, lines):
        """ Revokes the specified lines in the order.

        Iterates over the given lines and revokes the associated products, if possible.  Reports success if the product
        can be revoked, but may fail if the module cannot support revoking or process of revoking the product fails
        due to underlying services.

        Args:
            order (Order): The Order associated with the lines to be revoked.
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of revoking the products.
        """
        raise NotImplementedError("Revoke method not implemented!")

    @staticmethod
    def get_product_type(product):
        """Check for the product type.

        Oscar Products all have a type, and Fulfillment Modules will often be directly associated with them. This
        function will pull the type from the product, or the parent product. By design, Oscar Child Products do not have
        a product type, but inherit from their parents.

        Args:
            product (Product): A product this module may fulfill.

        Returns:
            ProductClass representing the type of this product or its parent.

        """
        return product.product_class if product.product_class is not None else product.parent.product_class


class EnrollmentFulfillmentModule(FulfillmentModule):
    """ Fulfillment Module for enrolling students after a product purchase.

    Allows the enrollment of a student via purchase of a 'seat'.

    """
    REQUEST_TIMEOUT = 5

    def get_supported_lines(self, order, lines):
        """ Return a list of lines that can be fulfilled through enrollment.

        Check each line in the order to see if it is a "Seat". Seats are fulfilled by enrolling students
        in a course, which is the sole functionality of this module. Any Seat product will be returned as
        a supported line in the order.

        Args:
            order (Order): The Order associated with the lines to be fulfilled
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of unmodified lines associated with "Seat" products.

        """
        supported_lines = []
        for line in lines:
            if self.get_product_type(line.product).name == 'Seat':
                supported_lines.append(line)
        return supported_lines

    def fulfill_product(self, order, lines):
        """ Fulfills the purchase of a 'seat' by enrolling the associated student.

        Uses the order and the lines to determine which courses to enroll a student in, and with certain
        certificate types. May result in an error if the Enrollment API cannot be reached, or if there is
        additional business logic errors when trying to enroll the student.

        Args:
            order (Order): The Order associated with the lines to be fulfilled. The user associated with the order
                is presumed to be the student to enroll in a course.
            lines (List of Lines): Order Lines, associated with purchased products in an Order. These should only
                be "Seat" products.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.

        """
        logger.info("Attempting to fulfill 'Seat' product types for order [%s]", order.number)

        enrollment_api_url = getattr(settings, 'ENROLLMENT_API_URL', None)
        api_key = getattr(settings, 'EDX_API_KEY', None)
        if not enrollment_api_url or not api_key:
            logger.error(
                "ENROLLMENT_API_URL and EDX_API_KEY must be set to use the EnrollmentFulfillmentModule"
            )
            for line in lines:
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)

        student = order.user.username
        for line in lines:
            try:
                certificate_type = line.product.attribute_values.get(attribute__name="certificate_type").value
                course_key = line.product.attribute_values.get(attribute__name="course_key").value
            except ProductAttributeValue.DoesNotExist:
                logger.error("Supported Seat Product does not have required attributes, [certificate_type, course_key]")
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
                continue

            data = {
                'user': student,
                'mode': certificate_type,
                'course_details': {
                    'course_id': course_key
                }
            }

            headers = {
                'Content-Type': 'application/json',
                'X-Edx-Api-Key': api_key,
            }

            try:
                response = requests.post(
                    enrollment_api_url,
                    data=json.dumps(data),
                    headers=headers,
                    timeout=self.REQUEST_TIMEOUT
                )

                if response.status_code == status.HTTP_200_OK:
                    logger.info("Success fulfilling line [%d] of order [%s].", line.id, order.number)
                    line.set_status(LINE.COMPLETE)
                else:
                    try:
                        data = response.json()
                        reason = data.get('message')
                    except Exception:   # pylint: disable=broad-except
                        reason = '(No detail provided.)'

                    logger.error(
                        "Unable to fulfill line [%d] of order [%s] due to a server-side error: %s", line.id,
                        order.number, reason
                    )
                    line.set_status(LINE.FULFILLMENT_SERVER_ERROR)
            except ConnectionError:
                logger.error(
                    "Unable to fulfill line [%d] of order [%s] due to a network problem", line.id, order.number
                )
                line.set_status(LINE.FULFILLMENT_NETWORK_ERROR)
            except Timeout:
                logger.error(
                    "Unable to fulfill line [%d] of order [%s] due to a request time out", line.id, order.number
                )
                line.set_status(LINE.FULFILLMENT_TIMEOUT_ERROR)
        logger.info("Finished fulfilling 'Seat' product types for order [%s]", order.number)
        return order, lines
