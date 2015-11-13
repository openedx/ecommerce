"""Fulfillment Modules with specific fulfillment logic per Product Type, or a Combination of Types

Fulfillment Modules are designed to allow specific fulfillment logic based on the type (or types) of products
in an Order.
"""
import abc
import json
import logging
import string
import random
import requests

from datetime import datetime
from django.conf import settings
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status

from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.analytics.utils import audit_log, parse_tracking_context
from ecommerce.extensions.fulfillment.status import LINE

logger = logging.getLogger(__name__)

Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
EnrollmentCode = get_model('order', 'EnrollmentCode')
Range = get_model('offer', 'Range')
Voucher = get_model('voucher', 'Voucher')


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


class EnrollmentCodeFulfillmentModule(BaseFulfillmentModule):
    """ Fulfillment Module for creating vouchers after a product purchase.

    Allows the enrollment of a student via purchase of an 'enrollment code'.
    """

    def generate_code_string(self, length):
        """
        Create a string of random characters of specified length

        Args:
            length: Defines the length of randomly generated string

        Returns:
            Randomly generated string that will be used as a voucher code
        """
        chars = [
            char for char in string.ascii_uppercase + string.digits + string.ascii_lowercase
            if char not in 'aAeEiIoOuU1l'
        ]

        return string.join((random.choice(chars) for i in range(length)), '')

    def supports_line(self, line):
        """
        Check whether the product in line is an Enrollment Code

        Args:
            line: Defines the length of randomly generated string

        Returns:
            Randomly generated string that will be used as a voucher code
        """
        return line.product.get_product_class().name == 'Enrollment code'

    def get_supported_lines(self, lines):
        """ Return a list of lines that can be fulfilled through enrollment code.

        Checks each line to determine if it is an "Enrollment Code". Enrollment codes are fulfilled
        by creating a voucher, which is the sole functionality of this module.
        Any Enrollment Code product will be returned as a supported line.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of unmodified lines associated with "Enrollment Code" products.
        """
        return [line for line in lines if self.supports_line(line)]

    def get_or_create_range_of_products(self, catalog):
        """ Return a range of Enrollment Code products that are part of a specific catalog.

        If range of products doesn't exist, new range will be created and associated with
        provided catalog ID.

        Args:
            catalog_ID: ID of the catalog associated with range

        Returns:
            Range of products associated with provided Catalog ID.
        """
        range_name = 'Range for {}'.format(unicode(catalog))
        product_range, created = Range.objects.get_or_create(
            name=range_name,
            catalog=catalog,
        )
        for product in product_range.all_products():
            product_range.add_product(product)
        return product_range

    def create_new_voucher(self, offer, line):
        """ Return a newly created voucher code that represents the offer.

        If randomly generated voucher code already exists, new code will be generated and reverified.

        Args:
            offer: offer associated with voucher
        """
        voucher_name = 'Enrollment Code for {}'.format(unicode(offer.condition.range.catalog))

        existing_voucher_codes = Voucher.objects.values('code')

        while True:
            voucher_code = self.generate_code_string(settings.REGISTRATION_CODE_LENGTH)
            if voucher_code not in existing_voucher_codes:
                break

        voucher = Voucher.objects.create(
            name=voucher_name,
            code=voucher_code,
            usage=unicode(line.product.attr.type),
            start_datetime=line.product.attr.start_date,
            end_datetime=line.product.attr.end_date
        )
        voucher.offers.add(offer)
        voucher.save()

        return voucher

    def get_or_create_enrollment_code(self, line):
        """ Return an enrollment code associated with the line item

        Args:
            line: line item associated with enrollment code
        """
        enrollment_code, created = EnrollmentCode.objects.get_or_create(
            order_line=line,
        )
        return enrollment_code

    def get_or_create_offer_condition(self, product_range):
        """ Return an offer condition for a product range.

        If offer condition doesn't exist, new condition will be created and associated with
        provided product range.

        Args:
            product range: Product range associated with the condition

        Returns:
            Offer Condition associated with provided Product Range.
        """
        offer_condition, created = Condition.objects.get_or_create(
            range=product_range,
            type=Condition.COUNT,
            value=1,
        )
        return offer_condition

    def get_or_create_offer_benefit(self, product_range):
        """ Return an offer benefit for a product range.

        If offer benefit doesn't exist, new benefit will be created and associated with
        provided product range.

        Args:
            product range: Product range associated with the benefit

        Returns:
            Offer Benefit associated with provided Product Range.
        """
        offer_benefit, created = Benefit.objects.get_or_create(
            range=product_range,
            type=Benefit.PERCENTAGE,
            value=100.00,
        )
        return offer_benefit

    def get_or_create_offer(self, catalog_id, offer_condition, offer_benefit):
        """ Return an offer for a catalog with condition and benefit.

        If offer doesn't exist, new offer will be created and associated with
        provided Offer condition and benefit.

        Args:
            offer condition: Offer condition associated with the offer
            offer benefit: Offer benefit associated with the offer

        Returns:
            Offer associated with provided Offer condition and benefit.
        """
        offer_name = "{} {}".format(settings.OFFER_NAME_PREFIX, catalog_id)
        offer, created = ConditionalOffer.objects.get_or_create(
            name=offer_name,
            offer_type=ConditionalOffer.VOUCHER,
            condition=offer_condition,
            benefit=offer_benefit,
        )
        return offer

    def fulfill_product(self, order, lines):
        """ Fulfills the purchase of an 'enrollment code' by creating a voucher.

        Uses the order and the lines to determine which courses to create a voucher for.

        Args:
            order (Order): The Order associated with the lines to be fulfilled. The client associated with the order
                will be the client to own a voucher.
            lines (List of Lines): Order Lines, associated with purchased products in an Order. These should only
                be "Enrollment Code" products.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.

        """
        logger.info("Attempting to fulfill 'Enrollment Code' product types for order [%s]", order.number)

        for line in lines:
            catalog = line.product.attr.catalog
            product_range = self.get_or_create_range_of_products(catalog)
            offer_condition = self.get_or_create_offer_condition(product_range)
            offer_benefit = self.get_or_create_offer_benefit(product_range)
            offer = self.get_or_create_offer(catalog.id, offer_condition, offer_benefit)
            for i in range(line.quantity):
                voucher = self.create_new_voucher(offer, line)
                enrollment_code = self.get_or_create_enrollment_code(line)
                enrollment_code.vouchers.add(voucher)
            line.set_status(LINE.COMPLETE)
        logger.info("Finished fulfilling 'Enrollment Code' product types for order [%s]", order.number)
        return order, lines

    def revoke_line(self, line):
        """ Revokes the specified line. Makes the voucher associated with the line inactive.

        Args:
            line (Line): Order Line to be revoked.

        Returns:
            True, if the voucher is deactivated; otherwise, False.
        """
        enrollment_code = self.get_or_create_enrollment_code(line)
        vouchers = enrollment_code.vouchers.all()
        if vouchers:
            vouchers.update(end_datetime=datetime.now())
            return True
        return False
