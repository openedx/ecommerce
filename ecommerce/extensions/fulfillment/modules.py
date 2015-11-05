"""Fulfillment Modules with specific fulfillment logic per Product Type, or a Combination of Types

Fulfillment Modules are designed to allow specific fulfillment logic based on the type (or types) of products
in an Order.
"""
import abc
import json
import logging

from django.conf import settings
from rest_framework import status
import requests
from requests.exceptions import ConnectionError, Timeout
from ecommerce.courses.utils import mode_for_seat

from ecommerce.extensions.analytics.utils import audit_log, parse_tracking_context
from ecommerce.extensions.fulfillment.status import LINE


logger = logging.getLogger(__name__)


class BaseFulfillmentModule(object):  # pragma: no cover
    """
    Base FulfillmentModule class for containing Product specific fulfillment logic.

    All modules should extend the FulfillmentModule and adhere to the defined contract.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def supports_line(self, line):
        """
        Returns True if the given Line can be fulfilled/revoked by this module.

        Args:
            line (Line): Line to be considered.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_supported_lines(self, lines):
        """ Return a list of supported lines

        Each Fulfillment Module is capable of fulfillment certain products. This function allows a preliminary
        check of which lines could be supported by this Fulfillment Module.

         By evaluating the lines, this will return a list of all the lines in the order that
         can be fulfilled by this module.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of lines, unmodified.
        """
        raise NotImplementedError("Line support method not implemented!")

    @abc.abstractmethod
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

    @abc.abstractmethod
    def revoke_line(self, line):
        """ Revokes the specified line.

        Args:
            line (Line): Order Line to be revoked.

        Returns:
            True, if the product is revoked; otherwise, False.
        """
        raise NotImplementedError("Revoke method not implemented!")


class EnrollmentFulfillmentModule(BaseFulfillmentModule):
    """ Fulfillment Module for enrolling students after a product purchase.

    Allows the enrollment of a student via purchase of a 'seat'.
    """

    def _post_to_enrollment_api(self, data, user):
        enrollment_api_url = settings.ENROLLMENT_API_URL
        timeout = settings.ENROLLMENT_FULFILLMENT_TIMEOUT
        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        __, client_id, ip = parse_tracking_context(user)

        if client_id:
            headers['X-Edx-Ga-Client-Id'] = client_id

        if ip:
            headers['X-Forwarded-For'] = ip

        return requests.post(enrollment_api_url, data=json.dumps(data), headers=headers, timeout=timeout)

    def supports_line(self, line):
        return line.product.get_product_class().name == 'Seat'

    def get_supported_lines(self, lines):
        """ Return a list of lines that can be fulfilled through enrollment.

        Checks each line to determine if it is a "Seat". Seats are fulfilled by enrolling students
        in a course, which is the sole functionality of this module. Any Seat product will be returned as
        a supported line.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of unmodified lines associated with "Seat" products.
        """
        return [line for line in lines if self.supports_line(line)]

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
        if not (enrollment_api_url and api_key):
            logger.error(
                'ENROLLMENT_API_URL and EDX_API_KEY must be set to use the EnrollmentFulfillmentModule'
            )
            for line in lines:
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)

            return order, lines

        for line in lines:
            try:
                mode = mode_for_seat(line.product)
                course_key = line.product.attr.course_key
            except AttributeError:
                logger.error("Supported Seat Product does not have required attributes, [certificate_type, course_key]")
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
                continue
            try:
                provider = line.product.attr.credit_provider
            except AttributeError:
                logger.debug("Seat [%d] has no credit_provider attribute. Defaulted to None.", line.product.id)
                provider = None

            data = {
                'user': order.user.username,
                'is_active': True,
                'mode': mode,
                'course_details': {
                    'course_id': course_key
                },
                'enrollment_attributes': [
                    {
                        'namespace': 'order',
                        'name': 'order_number',
                        'value': order.number
                    }
                ]
            }
            if provider:
                data['enrollment_attributes'].append(
                    {
                        'namespace': 'credit',
                        'name': 'provider_id',
                        'value': provider
                    }
                )
            try:
                response = self._post_to_enrollment_api(data, user=order.user)

                if response.status_code == status.HTTP_200_OK:
                    line.set_status(LINE.COMPLETE)

                    audit_log(
                        'line_fulfilled',
                        order_line_id=line.id,
                        order_number=order.number,
                        product_class=line.product.get_product_class().name,
                        course_id=course_key,
                        mode=mode,
                        user_id=order.user.id,
                        credit_provider=provider,
                    )
                else:
                    try:
                        data = response.json()
                        reason = data.get('message')
                    except Exception:  # pylint: disable=broad-except
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

    def revoke_line(self, line):
        try:
            logger.info('Attempting to revoke fulfillment of Line [%d]...', line.id)

            mode = mode_for_seat(line.product)
            course_key = line.product.attr.course_key
            data = {
                'user': line.order.user.username,
                'is_active': False,
                'mode': mode,
                'course_details': {
                    'course_id': course_key,
                },
            }

            response = self._post_to_enrollment_api(data, user=line.order.user)

            if response.status_code == status.HTTP_200_OK:
                audit_log(
                    'line_revoked',
                    order_line_id=line.id,
                    order_number=line.order.number,
                    product_class=line.product.get_product_class().name,
                    course_id=course_key,
                    certificate_type=getattr(line.product.attr, 'certificate_type', ''),
                    user_id=line.order.user.id
                )

                return True
            else:
                # check if the error / message are something we can recover from.
                data = response.json()
                detail = data.get('message', '(No details provided.)')
                if response.status_code == 400 and "Enrollment mode mismatch" in detail:
                    # The user is currently enrolled in different mode than the one
                    # we are refunding an order for.  Don't revoke that enrollment.
                    logger.info('Skipping revocation for line [%d]: %s', line.id, detail)
                    return True
                else:
                    logger.error('Failed to revoke fulfillment of Line [%d]: %s', line.id, detail)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to revoke fulfillment of Line [%d].', line.id)

        return False


class CouponFulfillmentModule(BaseFulfillmentModule):
    """ Fulfillment Module for coupons. """

    def supports_line(self, line):
        """
        Check whether the product in line is a Coupon

        Args:
            line (Line): Defines the length of randomly generated string

        Returns:
            True if the line contains product of product class Coupon.
            False otherwise.
        """
        return line.product.get_product_class().name == 'Coupon'

    def get_supported_lines(self, lines):
        """ Return a list of lines containing products with Coupon product class
        that can be fulfilled.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
        Returns:
            A supported list of unmodified lines associated with 'Coupon' products.
        """
        return [line for line in lines if self.supports_line(line)]

    def fulfill_product(self, order, lines):
        """ Fulfills the purchase of an 'coupon' products.

        Args:
            order (Order): The Order associated with the lines to be fulfilled.
            lines (List of Lines): Order Lines, associated with purchased products in an Order. These should only
                be 'Coupon' products.
        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.
        """
        logger.info("Attempting to fulfill 'Coupon' product types for order [%s]", order.number)

        for line in lines:
            line.set_status(LINE.COMPLETE)

        logger.info("Finished fulfilling 'Coupon' product types for order [%s]", order.number)
        return order, lines

    def revoke_line(self, line):
        raise NotImplementedError("Revoke method not implemented!")
