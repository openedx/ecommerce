"""Fulfillment Modules with specific fulfillment logic per Product Type, or a Combination of Types

Fulfillment Modules are designed to allow specific fulfillment logic based on the type (or types) of products
in an Order.
"""


import abc
import datetime
import json
import logging
from urllib.parse import urlencode, urljoin

import requests
import waffle
from django.conf import settings
from django.urls import reverse
from getsmarter_api_clients.geag import GetSmarterEnterpriseApiClient
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError  # pylint: disable=ungrouped-imports
from requests.exceptions import Timeout
from rest_framework import status

from ecommerce.core.constants import (
    DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    HUBSPOT_FORMS_INTEGRATION_ENABLE,
    ISO_8601_FORMAT
)
from ecommerce.core.url_utils import get_lms_enrollment_api_url, get_lms_entitlement_api_url
from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_info_from_catalog, mode_for_product
from ecommerce.enterprise.conditions import BasketAttributeType
from ecommerce.enterprise.mixins import EnterpriseDiscountMixin
from ecommerce.enterprise.utils import (
    create_enterprise_customer_user_consent,
    get_enterprise_customer_uuid_from_voucher,
    get_or_create_enterprise_customer_user
)
from ecommerce.extensions.analytics.utils import audit_log, parse_tracking_context
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.basket.models import BasketAttribute
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.voucher.models import OrderLineVouchers
from ecommerce.extensions.voucher.utils import create_vouchers
from ecommerce.notifications.notifications import send_notification

BasketAttributeType = get_model('basket', 'BasketAttributeType')
Benefit = get_model('offer', 'Benefit')
Option = get_model('catalogue', 'Option')
Product = get_model('catalogue', 'Product')
Range = get_model('offer', 'Range')
Voucher = get_model('voucher', 'Voucher')
StockRecord = get_model('partner', 'StockRecord')
logger = logging.getLogger(__name__)


class BaseFulfillmentModule(metaclass=abc.ABCMeta):  # pragma: no cover
    """
    Base FulfillmentModule class for containing Product specific fulfillment logic.

    All modules should extend the FulfillmentModule and adhere to the defined contract.
    """

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
    def fulfill_product(self, order, lines, email_opt_in=False):
        """ Fulfills the specified lines in the order.

        Iterates over the given lines and fulfills the associated products. Will report success if the product can
        be fulfilled, but may fail if the module cannot support fulfillment of the specified product, or there is
        an error with the services required to fulfill the current product.

        Args:
            order (Order): The Order associated with the lines to be fulfilled
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
            email_opt_in (bool): Whether to opt the user in to emails as part
                of fulfillment. Defaults to false. Used for email opt in with
                bundle (program) purchases.

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


class DonationsFromCheckoutTestFulfillmentModule(BaseFulfillmentModule):
    """
    Fulfillment module for fulfilling donations as a part of LEARNER-2842 - Test Donations on Checkout.
    If that test, or any follow up tests around donations at checkout are not implemented, this module will be reverted.
    Don't use this code for your own purposes, thanks.
    """
    def supports_line(self, line):
        """
        Returns True if the given Line has a donation product.
        """
        return line.product.get_product_class().name == DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME

    def get_supported_lines(self, lines):
        """ Return a list of supported lines (that contain a donation product)

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of lines, unmodified.
        """
        return [line for line in lines if self.supports_line(line)]

    def fulfill_product(self, order, lines, email_opt_in=False):
        """ Fulfills the specified lines in the order.
        Marks the line status as complete. Does not change anything else.

        Args:
            order (Order): The Order associated with the lines to be fulfilled
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
            email_opt_in (bool): Whether the user should be opted in to emails
                as part of the fulfillment. Defaults to False.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.

        """
        for line in lines:
            line.set_status(LINE.COMPLETE)
        return order, lines

    def revoke_line(self, line):
        """ Revokes the specified line.
        (Returning true to avoid unnecessary errors)

        Args:
            line (Line): Order Line to be revoked.

        Returns:
            True, if the product is revoked; otherwise, False.
        """
        return True


class EnrollmentFulfillmentModule(EnterpriseDiscountMixin, BaseFulfillmentModule):
    """ Fulfillment Module for enrolling students after a product purchase.

    Allows the enrollment of a student via purchase of a 'seat'.

    Arguments:
        usage (string): A description of why data is being posted to the enrollment API. This will be included in log
            messages if the LMS user id cannot be found.
    """

    def _post_to_enrollment_api(self, data, user, usage):
        enrollment_api_url = get_lms_enrollment_api_url()
        timeout = settings.ENROLLMENT_FULFILLMENT_TIMEOUT
        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        __, client_id, ip = parse_tracking_context(user, usage=usage)

        if client_id:
            headers['X-Edx-Ga-Client-Id'] = client_id

        if ip:
            headers['X-Forwarded-For'] = ip

        return requests.post(enrollment_api_url, data=json.dumps(data), headers=headers, timeout=timeout)

    def _add_enterprise_data_to_enrollment_api_post(self, data, order):
        """ Augment enrollment api POST data with enterprise specific data.

        Checks the order to see if there was a discount applied and if that discount
        was associated with an EnterpriseCustomer. If so, enterprise specific data
        is added to the POST data and an EnterpriseCustomerUser model is created if
        one does not already exist.

        Arguments:
            data (dict): The POST data for the enrollment API.
            order (Order): The order.
        """
        # Collect the EnterpriseCustomer UUID from the coupon, if any.
        enterprise_customer_uuid = None
        for discount in order.discounts.all():
            if discount.voucher:
                logger.info("Getting enterprise_customer_uuid from discount voucher for order [%s]", order.number)
                enterprise_customer_uuid = get_enterprise_customer_uuid_from_voucher(discount.voucher)
                logger.info(
                    "enterprise_customer_uuid on discount voucher for order [%s] is [%s]",
                    order.number, enterprise_customer_uuid
                )

            if enterprise_customer_uuid is not None:
                logger.info(
                    "Adding linked_enterprise_customer to data with enterprise_customer_uuid [%s] for order [%s]",
                    enterprise_customer_uuid, order.number
                )
                data['linked_enterprise_customer'] = str(enterprise_customer_uuid)
                break
        # If an EnterpriseCustomer UUID is associated with the coupon, create an EnterpriseCustomerUser
        # on the Enterprise service if one doesn't already exist.
        if enterprise_customer_uuid is not None:
            logger.info(
                "Getting or creating enterprise_customer_user "
                "for site [%s], enterprise customer [%s], and username [%s], for order [%s]",
                order.site, enterprise_customer_uuid, order.user.username, order.number
            )
            get_or_create_enterprise_customer_user(
                order.site,
                enterprise_customer_uuid,
                order.user.username
            )
            logger.info(
                "Finished get_or_create enterpruise customer user for order [%s]",
                order.number
            )

    def supports_line(self, line):
        return line.product.is_seat_product

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

    def fulfill_product(self, order, lines, email_opt_in=False):  # pylint: disable=too-many-statements
        """ Fulfills the purchase of a 'seat' by enrolling the associated student.

        Uses the order and the lines to determine which courses to enroll a student in, and with certain
        certificate types. May result in an error if the Enrollment API cannot be reached, or if there is
        additional business logic errors when trying to enroll the student.

        Args:
            order (Order): The Order associated with the lines to be fulfilled. The user associated with the order
                is presumed to be the student to enroll in a course.
            lines (List of Lines): Order Lines, associated with purchased products in an Order. These should only
                be "Seat" products.
            email_opt_in (bool): Whether the user should be opted in to emails
                as part of the fulfillment. Defaults to False.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.

        """
        logger.info("Attempting to fulfill 'Seat' product types for order [%s]", order.number)

        api_key = getattr(settings, 'EDX_API_KEY', None)
        if not api_key:
            logger.error(
                'EDX_API_KEY must be set to use the EnrollmentFulfillmentModule'
            )
            for line in lines:
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)

            return order, lines

        for line in lines:
            try:
                mode = mode_for_product(line.product)
                course_key = line.product.attr.course_key
            except AttributeError:
                logger.error("Supported Seat Product does not have required attributes, [certificate_type, course_key]")
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
                continue
            try:
                provider = line.product.attr.credit_provider
            except AttributeError:
                logger.error("Seat [%d] has no credit_provider attribute. Defaulted to None.", line.product.id)
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
                    },
                    {
                        'namespace': 'order',
                        'name': 'date_placed',
                        'value': order.date_placed.strftime(ISO_8601_FORMAT)
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
                logger.info("Adding enterprise data to enrollment api post for order [%s]", order.number)
                self._add_enterprise_data_to_enrollment_api_post(data, order)
                logger.info("Updating orderline with enterprise discount metadata for order [%s]", order.number)
                self.update_orderline_with_enterprise_discount_metadata(order, line)

                # Post to the Enrollment API. The LMS will take care of posting a new EnterpriseCourseEnrollment to
                # the Enterprise service if the user+course has a corresponding EnterpriseCustomerUser.
                logger.info("Posting to enrollment api for order [%s]", order.number)
                response = self._post_to_enrollment_api(data, user=order.user, usage='fulfill enrollment')
                logger.info("Finished posting to enrollment api for order [%s]", order.number)

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
                        "Fulfillment of line [%d] on order [%s] failed with status code [%d]: %s",
                        line.id, order.number, response.status_code, reason
                    )
                    order.notes.create(message=reason, note_type='Error')
                    line.set_status(LINE.FULFILLMENT_SERVER_ERROR)
            except ReqConnectionError:
                logger.error(
                    "Unable to fulfill line [%d] of order [%s] due to a network problem", line.id, order.number
                )
                order.notes.create(message='Fulfillment of order failed due to a network problem.', note_type='Error')
                line.set_status(LINE.FULFILLMENT_NETWORK_ERROR)
            except Timeout:
                logger.error(
                    "Unable to fulfill line [%d] of order [%s] due to a request time out", line.id, order.number
                )
                order.notes.create(message='Fulfillment of order failed due to a request time out.', note_type='Error')
                line.set_status(LINE.FULFILLMENT_TIMEOUT_ERROR)
        logger.info("Finished fulfilling 'Seat' product types for order [%s]", order.number)
        return order, lines

    def revoke_line(self, line):
        try:
            logger.info('Attempting to revoke fulfillment of Line [%d]...', line.id)

            mode = mode_for_product(line.product)
            course_key = line.product.attr.course_key
            data = {
                'user': line.order.user.username,
                'is_active': False,
                'mode': mode,
                'course_details': {
                    'course_id': course_key,
                },
            }

            response = self._post_to_enrollment_api(data, user=line.order.user, usage='revoke enrollment')

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
            # check if the error / message are something we can recover from.
            data = response.json()
            detail = data.get('message', '(No details provided.)')
            if response.status_code == 400 and "Enrollment mode mismatch" in detail:
                # The user is currently enrolled in different mode than the one
                # we are refunding an order for.  Don't revoke that enrollment.
                logger.info('Skipping revocation for line [%d]: %s', line.id, detail)
                return True
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
            line (Line): Line to be considered.

        Returns:
            True if the line contains product of product class Coupon.
            False otherwise.
        """
        return line.product.is_coupon_product

    def get_supported_lines(self, lines):
        """ Return a list of lines containing products with Coupon product class
        that can be fulfilled.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
        Returns:
            A supported list of unmodified lines associated with 'Coupon' products.
        """
        return [line for line in lines if self.supports_line(line)]

    def fulfill_product(self, order, lines, email_opt_in=False):
        """ Fulfills the purchase of an 'coupon' products.

        Args:
            order (Order): The Order associated with the lines to be fulfilled.
            lines (List of Lines): Order Lines, associated with purchased products in an Order. These should only
                be 'Coupon' products.
            email_opt_in (bool): Whether the user should be opted in to emails
                as part of the fulfillment. Defaults to False.
        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.
        """
        logger.info("Attempting to fulfill 'Coupon' product types for order [%s]", order.number)

        for line in lines:
            line.set_status(LINE.COMPLETE)

        logger.info("Finished fulfilling 'Coupon' product types for order [%s]", order.number)
        return order, lines

    def revoke_line(self, line):
        """ Revokes the specified line.

        Args:
            line (Line): Order Line to be revoked.

        Returns:
            True, if the product is revoked; otherwise, False.
        """
        raise NotImplementedError("Revoke method not implemented!")


class EnrollmentCodeFulfillmentModule(BaseFulfillmentModule):
    def supports_line(self, line):
        """
        Check whether the product in line is an Enrollment code.

        Args:
            line (Line): Line to be considered.

        Returns:
            True if the line contains an Enrollment code.
            False otherwise.
        """
        return line.product.is_enrollment_code_product

    def get_supported_lines(self, lines):
        """ Return a list of lines containing Enrollment code products that can be fulfilled.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
        Returns:
            A supported list of unmodified lines associated with an Enrollment code product.
        """
        return [line for line in lines if self.supports_line(line)]

    def fulfill_product(self, order, lines, email_opt_in=False):
        """ Fulfills the purchase of an Enrollment code product.
        For each line creates number of vouchers equal to that line's quantity. Creates a new OrderLineVouchers
        object to tie the order with the created voucher and adds the vouchers to the coupon's total vouchers.

        Args:
            order (Order): The Order associated with the lines to be fulfilled.
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
            email_opt_in (bool): Whether the user should be opted in to emails
                as part of the fulfillment. Defaults to False.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.
        """
        msg = "Attempting to fulfill '{product_class}' product types for order [{order_number}]".format(
            product_class=ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
            order_number=order.number
        )
        logger.info(msg)

        for line in lines:
            name = 'Enrollment Code Range for {}'.format(line.product.attr.course_key)
            seat = Product.objects.filter(
                attributes__name='course_key',
                attribute_values__value_text=line.product.attr.course_key
            ).get(
                attributes__name='certificate_type',
                attribute_values__value_text=line.product.attr.seat_type
            )
            _range, created = Range.objects.get_or_create(name=name)
            if created:
                _range.add_product(seat)

            stock_record = StockRecord.objects.get(product=seat, partner=seat.course.partner)
            coupon_catalog = CouponViewSet.get_coupon_catalog([stock_record.id], seat.course.partner)
            _range.catalog = coupon_catalog
            _range.save()

            vouchers = create_vouchers(
                name=str('Enrollment code voucher [{}]').format(line.product.title),
                benefit_type=Benefit.PERCENTAGE,
                benefit_value=100,
                catalog=coupon_catalog,
                coupon=seat,
                end_datetime=settings.ENROLLMENT_CODE_EXIPRATION_DATE,
                enterprise_customer=None,
                enterprise_customer_catalog=None,
                quantity=line.quantity,
                start_datetime=datetime.datetime.now(),
                voucher_type=Voucher.SINGLE_USE,
                _range=_range
            )

            line_vouchers = OrderLineVouchers.objects.create(line=line)
            for voucher in vouchers:
                line_vouchers.vouchers.add(voucher)

            line.set_status(LINE.COMPLETE)

        # if the HubSpot integration is enabled and this is an Enterprise purchase then transmit information about the
        # order over to HubSpot
        if waffle.switch_is_active(HUBSPOT_FORMS_INTEGRATION_ENABLE) and self.determine_if_enterprise_purchase(order):
            self.send_fulfillment_data_to_hubspot(order)

        self.send_email(order)
        logger.info("Finished fulfilling 'Enrollment code' product types for order [%s]", order.number)
        return order, lines

    def determine_if_enterprise_purchase(self, order):
        """ Added as part of ENT-2317. Inspects the order/basket to determine if the purchaser checked the "purchased
        on behalf of my company" checkbox at time of purchase, which drives whether we should send this order
         information over to HubSpot.

            Args:
                order (Order): The Order associated with the lines to be fulfilled.

            Returns:
                A boolean reflecting whether or not this purchase was made on behalf of a company or organization driven
                by the value of the associated attribute for the order/basket in question.
        """
        enterprise_purchase = False
        try:
            # extract basket info needed to determine if purchase was made on behalf of an Enterprise
            basket_attrib_purchaser = BasketAttribute.objects.get(
                basket=order.basket,
                attribute_type=BasketAttributeType.objects.get(name=PURCHASER_BEHALF_ATTRIBUTE))
            enterprise_purchase = basket_attrib_purchaser.value_text == "True"
        except (BasketAttribute.DoesNotExist, BasketAttributeType.DoesNotExist):
            logger.exception("Error occurred attempting to retrieve Basket Attribute '%s' from basket for order [%s]",
                             PURCHASER_BEHALF_ATTRIBUTE, order.number)

        return enterprise_purchase

    def send_fulfillment_data_to_hubspot(self, order):
        """ Added as part of ENT-2317. Sends fulfillment data to the HubSpot Form API with info about the purchase.

            Args:
                order (Order): The Order associated with the lines to be fulfilled.

            Returns:
                The response from the requests call. Primarily being used for unit testing.
        """
        response = ""
        try:
            headers = {"Content-Type": 'application/x-www-form-urlencoded'}
            # Build the URI for the HubSpot Forms API. See more here:
            # https://developers.hubspot.com/docs/methods/forms/submit_form which takes the form from
            # 'https://forms.hubspot.com/uploads/form/v2/{portal_id}/{form_id}?&'
            endpoint = "{}{}/{}?&".format(
                settings.HUBSPOT_FORMS_API_URI, settings.HUBSPOT_PORTAL_ID, settings.HUBSPOT_SALES_LEAD_FORM_GUID)
            data = self.get_order_fulfillment_data_for_hubspot(order)

            logger.info("Sending data to HubSpot for order [%s]", order.number)
            response = requests.post(url=endpoint, data=data, headers=headers, timeout=1)
            logger.debug("HubSpot response: %d", response.status_code)
        except Timeout:
            logger.error("Timeout occurred attempting to send data to HubSpot for order [%s]", order.number)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error occurred attempting to send data to HubSpot for order [%s]", order.number)

        return response

    def get_order_fulfillment_data_for_hubspot(self, order):
        """ Added as part of ENT-2317. Retrieves any data needed to build the URL Encoded request body for the HubSpot
        API Forms request we will be submitting. Information we will be sending to HubSpot includes:
            - First and Last name
            - Email
            - Course Number and Name purchased
            - Quantity purchased
            - Total dollar amount
            - Company/Organization
            - Address

            Args:
                order (Order): The Order associated with the lines to be fulfilled.

            Returns:
                A URL encoded string that will be the body of the request are sending to HubSpot containing
                fulfillment data about the order that was just processed.
        """
        logger.info("Gathering fulfillment data for submission to HubSpot for order [%s]", order.number)

        # need to do this to be able to grab the organization/company name, this isn't available in the order/lines
        organization = ""
        try:
            organization = BasketAttribute.objects.get(
                basket=order.basket,
                attribute_type=BasketAttributeType.objects.get(name="organization"))
        except (BasketAttribute.DoesNotExist, BasketAttributeType.DoesNotExist):
            logger.exception("Error occurred attempting to retrieve Basket Attribute 'organization' from basket for "
                             "order [%s]", order.number)

        # need to build out the address accordingly
        street_address = order.billing_address.line1
        # check if 'line2' is empty, if not then make sure we include that in the address info
        if order.billing_address.line2:
            street_address = "{}, {}".format(order.billing_address.line1, order.billing_address.line2)

        # When filling our our order page and selecting "United States" the string that gets populated in
        # order.billing_address.country.name is 'United States of America'. This will cause the mailing country to not
        # be populated on the HubSpot side in the form submission as 'United States of America' does not appear to
        # match what HubSpot is looking for. I did some digging in the form attributes and it looks like the HubSpot
        # side may be looking for 'United States'.
        #
        # I tested the theory below and changed it from 'United States of America' to 'United States' and the mailing
        # country was populated in the contact on form submission.
        country_name = order.billing_address.country.name
        if country_name == 'United States of America':
            country_name = 'United States'

        # get course name and number purchased from order information
        product = order.lines.first().product
        course = Course.objects.get(id=product.attr.course_key)

        data = urlencode({
            'firstname': order.billing_address.first_name,
            'lastname': order.billing_address.last_name,
            'email': order.email,
            'address': street_address,
            'city': order.billing_address.line4,
            'state': order.billing_address.state,
            'country': country_name,
            'company': organization.value_text,
            'deal_value': order.total_incl_tax,
            'ecommerce_course_name': course.name,
            'ecommerce_course_id': course.id,
            'bulk_purchase_quantity': order.num_items
        })

        return data

    def revoke_line(self, line):
        """ Revokes the specified line.

        Args:
            line (Line): Order Line to be revoked.

        Returns:
            True, if the product is revoked; otherwise, False.
        """
        raise NotImplementedError("Revoke method not implemented!")

    def send_email(self, order):
        """ Sends an email with enrollment code order information. """
        # Note (multi-courses): Change from a course_name to a list of course names.
        product = order.lines.first().product
        course = Course.objects.get(id=product.attr.course_key)
        receipt_page_url = get_receipt_page_url(
            None,
            order_number=order.number,
            site_configuration=order.site.siteconfiguration
        )
        send_notification(
            order.user,
            'ORDER_WITH_CSV',
            context={
                'contact_url': order.site.siteconfiguration.build_lms_url('/contact'),
                'course_name': course.name,
                'download_csv_link': order.site.siteconfiguration.build_ecommerce_url(
                    reverse('coupons:enrollment_code_csv', args=[order.number])
                ),
                'enrollment_code_title': product.title,
                'lms_url': order.site.siteconfiguration.build_lms_url(),
                'order_number': order.number,
                'partner_name': order.site.siteconfiguration.partner.name,
                'receipt_page_url': receipt_page_url,
                'order_history_url': order.site.siteconfiguration.build_lms_url('account/settings'),
            },
            site=order.site
        )


class CourseEntitlementFulfillmentModule(EnterpriseDiscountMixin, BaseFulfillmentModule):
    """ Fulfillment Module for granting students an entitlement.
    Allows the entitlement of a student via purchase of a 'Course Entitlement'.
    """

    def supports_line(self, line):
        return line.product.is_course_entitlement_product and not line.product.is_executive_education_2u_product

    def get_supported_lines(self, lines):
        """ Return a list of lines that can be fulfilled.
        Checks each line to determine if it is a "Course Entitlement". Entitlements are fulfilled by granting students
        an entitlement in a course, which is the sole functionality of this module.
        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
        Returns:
            A supported list of unmodified lines associated with "Course Entitlement" products.
        """
        return [line for line in lines if self.supports_line(line)]

    def _create_enterprise_customer_user(self, order):
        """
        Create the enterprise customer user if an EnterpriseCustomer UUID is associated in the order's discount voucher.
        """
        enterprise_customer_uuid = None
        for discount in order.discounts.all():
            if discount.voucher:
                enterprise_customer_uuid = get_enterprise_customer_uuid_from_voucher(discount.voucher)
            if enterprise_customer_uuid is not None:
                get_or_create_enterprise_customer_user(
                    order.site,
                    enterprise_customer_uuid,
                    order.user.username
                )
                break

    def fulfill_product(self, order, lines, email_opt_in=False):
        """ Fulfills the purchase of a 'Course Entitlement'.
        Uses the order and the lines to determine which courses to grant an entitlement for, and with certain
        certificate types. May result in an error if the Entitlement API cannot be reached, or if there is
        additional business logic errors when trying grant the entitlement.

        Updates the user's email preferences based on email_opt_in as a side effect.

        Args:
            order (Order): The Order associated with the lines to be fulfilled. The user associated with the order
                is presumed to be the student to grant an entitlement.
            lines (List of Lines): Order Lines, associated with purchased products in an Order. These should only
                be "Course Entitlement" products.
            email_opt_in (bool): Whether the user should be opted in to emails
                as part of the fulfillment. Defaults to False.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.
        """
        logger.info('Attempting to fulfill "Course Entitlement" product types for order [%s]', order.number)

        for line in lines:
            try:
                mode = mode_for_product(line.product)
                UUID = line.product.attr.UUID
            except AttributeError:
                logger.error('Entitlement Product does not have required attributes, [certificate_type, UUID]')
                line.set_status(LINE.FULFILLMENT_CONFIGURATION_ERROR)
                continue

            data = {
                'user': order.user.username,
                'course_uuid': UUID,
                'mode': mode,
                'order_number': order.number,
                'email_opt_in': email_opt_in,
            }

            try:
                self._create_enterprise_customer_user(order)
                self.update_orderline_with_enterprise_discount_metadata(order, line)
                entitlement_option = Option.objects.get(code='course_entitlement')

                api_client = line.order.site.siteconfiguration.oauth_api_client
                entitlement_url = urljoin(get_lms_entitlement_api_url(), 'entitlements/')

                # POST to the Entitlement API.
                response = api_client.post(entitlement_url, json=data)
                response.raise_for_status()
                response = response.json()
                line.attributes.create(option=entitlement_option, value=response['uuid'])
                line.set_status(LINE.COMPLETE)

                audit_log(
                    'line_fulfilled',
                    order_line_id=line.id,
                    order_number=order.number,
                    product_class=line.product.get_product_class().name,
                    UUID=UUID,
                    mode=mode,
                    user_id=order.user.id,
                )
            except (Timeout, ReqConnectionError):
                logger.exception(
                    'Unable to fulfill line [%d] of order [%s] due to a network problem', line.id, order.number
                )
                order.notes.create(message='Fulfillment of order failed due to a network problem.', note_type='Error')
                line.set_status(LINE.FULFILLMENT_NETWORK_ERROR)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    'Unable to fulfill line [%d] of order [%s]', line.id, order.number
                )
                order.notes.create(message='Fulfillment of order failed due to an Exception.', note_type='Error')
                line.set_status(LINE.FULFILLMENT_SERVER_ERROR)

        logger.info('Finished fulfilling "Course Entitlement" product types for order [%s]', order.number)
        return order, lines

    def revoke_line(self, line):
        try:
            logger.info('Attempting to revoke fulfillment of Line [%d]...', line.id)

            UUID = line.product.attr.UUID
            entitlement_option = Option.objects.get(code='course_entitlement')
            course_entitlement_uuid = line.attributes.get(option=entitlement_option).value

            api_client = line.order.site.siteconfiguration.oauth_api_client
            entitlement_url = urljoin(
                get_lms_entitlement_api_url(), f"entitlements/{course_entitlement_uuid}/"
            )

            # DELETE to the Entitlement API.
            resp = api_client.delete(entitlement_url)
            resp.raise_for_status()

            audit_log(
                'line_revoked',
                order_line_id=line.id,
                order_number=line.order.number,
                product_class=line.product.get_product_class().name,
                UUID=UUID,
                certificate_type=getattr(line.product.attr, 'certificate_type', ''),
                user_id=line.order.user.id
            )

            return True
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to revoke fulfillment of Line [%d].', line.id)

        return False


class ExecutiveEducation2UFulfillmentModule(BaseFulfillmentModule):
    """
    Fulfillment module for fulfilling orders for Executive Education (2U) products.
    """

    @property
    def get_smarter_client(self):
        return GetSmarterEnterpriseApiClient(
            client_id=settings.GET_SMARTER_OAUTH2_KEY,
            client_secret=settings.GET_SMARTER_OAUTH2_SECRET,
            provider_url=settings.GET_SMARTER_OAUTH2_PROVIDER_URL,
            api_url=settings.GET_SMARTER_API_URL
        )

    def supports_line(self, line):
        """
        Returns True if the given Line has a Executive Education (2U) product.
        """
        return line.product.is_executive_education_2u_product

    def get_supported_lines(self, lines):
        """ Return a list of supported lines.

        Args:
            lines (List of Lines): Order Lines, associated with purchased products in an Order.

        Returns:
            A supported list of lines, unmodified.
        """
        return [line for line in lines if self.supports_line(line)]

    def _create_enterprise_allocation_payload(
        self,
        order,
        line,
        fulfillment_details,
        currency='USD'
    ):
        # A variant_id attribute must exist on the product
        variant_id = getattr(line.product.attr, 'variant_id')

        # This will be the offer that was applied. We will let an error be thrown if this doesn't exist.
        discount = order.discounts.first()
        enterprise_customer_uuid = str(discount.offer.condition.enterprise_customer_uuid)
        data_share_consent = fulfillment_details.get('data_share_consent', None)

        payload = {
            'payment_reference': order.number,
            'enterprise_customer_uuid': enterprise_customer_uuid,
            'currency': currency,
            'order_items': [
                {
                    # productId will be the variant id from product details
                    'productId': variant_id,
                    'quantity': 1,
                    'normalPrice': line.line_price_before_discounts_excl_tax,
                    'discount': line.line_price_before_discounts_excl_tax - line.line_price_excl_tax,
                    'finalPrice': line.line_price_excl_tax
                }
            ],
            **fulfillment_details.get('address', {}),
            **fulfillment_details.get('user_details', {}),
            'terms_accepted_at': fulfillment_details.get('terms_accepted_at', ''),
        }
        if data_share_consent:
            payload['data_share_consent'] = data_share_consent

        return payload

    def _create_enterprise_customer_user_consent(
        self,
        order,
        line,
        fulfillment_details
    ):
        data_share_consent = fulfillment_details.get('data_share_consent', None)
        course_info = get_course_info_from_catalog(order.site, line.product)
        if data_share_consent and course_info:
            discount = order.discounts.first()
            enterprise_customer_uuid = str(discount.offer.condition.enterprise_customer_uuid)
            create_enterprise_customer_user_consent(
                site=order.site,
                enterprise_customer_uuid=enterprise_customer_uuid,
                course_id=course_info['key'],
                username=order.user.username
            )

    def _get_fulfillment_details(self, order):
        fulfillment_details_note = order.notes.filter(note_type='Fulfillment Details').first()
        if not fulfillment_details_note:
            return None

        try:
            return json.loads(fulfillment_details_note.message)
        except ValueError:
            logger.exception('Error deserializing fulfillment details for order [%s]', order.number)
            return None

    def fulfill_product(self, order, lines, email_opt_in=False):
        """ Fulfills the specified lines in the order.

        Args:
            order (Order): The Order associated with the lines to be fulfilled
            lines (List of Lines): Order Lines, associated with purchased products in an Order.
            email_opt_in (bool): Whether the user should be opted in to emails
                as part of the fulfillment. Defaults to False.

        Returns:
            The original set of lines, with new statuses set based on the success or failure of fulfillment.

        """

        lines = [line for line in lines if self.supports_line(line)]

        logger.info('Attempting to fulfill Executive Education (2U) product for order [%s]', order.number)

        # A note with fulfillment details should have been created at the time of order placement
        fulfillment_details = self._get_fulfillment_details(order)
        if not fulfillment_details:
            logger.exception(
                'Unable to fulfill order [%s] due to missing or malformed fulfillment details.',
                order.number
            )

            for line in lines:
                line.set_status(LINE.FULFILLMENT_SERVER_ERROR)
            return order, lines

        for line in lines:
            product = line.product

            allocation_payload = self._create_enterprise_allocation_payload(
                order=order,
                line=line,
                fulfillment_details=fulfillment_details
            )

            try:
                self._create_enterprise_customer_user_consent(
                    order=order,
                    line=line,
                    fulfillment_details=fulfillment_details
                )
                self.get_smarter_client.create_enterprise_allocation(**allocation_payload)
            except Exception as ex:  # pylint: disable=broad-except
                reason = ''
                try:
                    reason = ex.response.json()
                except:  # pylint: disable=bare-except
                    pass

                logger.exception(
                    '[ExecutiveEducation2UFulfillmentModule] Fulfillment of line [%d] on '
                    'order [%s] failed. Reason: %s. Fulfillment details: %s.',
                    line.id, order.number, reason, fulfillment_details,
                )
                line.set_status(LINE.FULFILLMENT_SERVER_ERROR)
            else:
                audit_log(
                    'line_fulfilled',
                    order_line_id=line.id,
                    order_number=order.number,
                    product_class=line.product.get_product_class().name,
                    course_uuid=getattr(product.attr, 'UUID', ''),
                    mode=getattr(product.attr, 'certificate_type', ''),
                    user_id=order.user.id,
                )
                line.set_status(LINE.COMPLETE)

        if all([line.status == LINE.COMPLETE for line in lines]):
            logger.info(
                'All lines for order [%s] were fulfilled, deleting note with fulfillment details.',
                order.number
            )
            order.notes.filter(note_type='Fulfillment Details').delete()

        return order, lines

    def revoke_line(self, line):
        """ Revokes the specified line.

        Args:
            line (Line): Order Line to be revoked.

        Returns:
            True, if the product is revoked; otherwise, False.
        """
        raise NotImplementedError("Revoke method not implemented!")
