from __future__ import unicode_literals

import json
import logging

import requests
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from edx_rest_api_client.exceptions import SlumberHttpBaseException
from oscar.core.loading import get_model

from ecommerce.core.constants import ENROLLMENT_CODE_SEAT_TYPES
from ecommerce.courses.utils import mode_for_seat

logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class LMSPublisher(object):
    timeout = settings.COMMERCE_API_TIMEOUT

    def get_seat_expiration(self, seat):
        if not seat.expires or 'professional' in getattr(seat.attr, 'certificate_type', ''):
            return None

        return seat.expires.isoformat()

    def get_course_verification_deadline(self, course):
        return course.verification_deadline.isoformat() if course.verification_deadline else None

    def serialize_seat_for_commerce_api(self, seat):
        """ Serializes a course seat product to a dict that can be further serialized to JSON. """
        stock_record = seat.stockrecords.first()

        bulk_sku = None
        if getattr(seat.attr, 'certificate_type', '') in ENROLLMENT_CODE_SEAT_TYPES:
            enrollment_code = seat.course.enrollment_code_product
            if enrollment_code:
                bulk_sku = enrollment_code.stockrecords.first().partner_sku

        return {
            'name': mode_for_seat(seat),
            'currency': stock_record.price_currency,
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'bulk_sku': bulk_sku,
            'expires': self.get_seat_expiration(seat),
        }

    def _publish_creditcourse(self, course):
        """Creates or updates a CreditCourse object on the LMS."""
        course_id = course.id
        data = {
            'course_key': course_id,
            'enabled': True
        }

        course.site.siteconfiguration.credit_api_client.courses(course_id).put(data)

    def publish(self, course, access_token=None):
        """ Publish course commerce data to LMS.

        Uses the Commerce API to publish course modes, prices, and SKUs to LMS. Uses
        CreditCourse API endpoints to publish CreditCourse data to LMS when necessary.

        Arguments:
            course (Course): Course to be published.

        Keyword Arguments:
            access_token (str): Access token used when publishing CreditCourse data to the LMS.

        Returns:
            None, if publish operation succeeded; otherwise, error message.
        """

        course_id = course.id
        error_message = _('Failed to publish commerce data for {course_id} to LMS.').format(course_id=course_id)

        name = course.name
        verification_deadline = self.get_course_verification_deadline(course)
        modes = [self.serialize_seat_for_commerce_api(seat) for seat in course.seat_products]

        if 'credit' in [mode['name'] for mode in modes]:
            try:
                self._publish_creditcourse(course)
                logger.info('Successfully published CreditCourse for [%s] to LMS.', course_id)
            except SlumberHttpBaseException as e:
                # Note that %r is used to log the repr() of the response content, which may sometimes
                # contain non-ASCII Unicode. We don't know (or want to guess) the encoding, so using %r will log the
                # raw bytes of the message, freeing us from the possibility of encoding errors.
                logger.exception(
                    'Failed to publish CreditCourse for [%s] to LMS. Status was [%d]. Body was %r.',
                    course_id,
                    e.response.status_code,
                    e.content
                )
                return error_message
            except:  # pylint: disable=bare-except
                logger.exception('Failed to publish CreditCourse for [%s] to LMS.', course_id)
                return error_message

        data = {
            'id': course_id,
            'name': name,
            'verification_deadline': verification_deadline,
            'modes': modes,
        }

        url = '{}/courses/{}/'.format(course.site.siteconfiguration.commerce_api_url.rstrip('/'), course_id)

        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        try:
            response = requests.put(url, data=json.dumps(data), headers=headers, timeout=self.timeout)
            if response.ok:
                logger.info('Successfully published commerce data for [%s].', course_id)
                return
            else:
                logger.error('Failed to publish commerce data for [%s] to LMS. Status was [%d]. Body was [%s].',
                             course_id, response.status_code, response.content)

                return self._parse_error(response, error_message)

        except:  # pylint: disable=bare-except
            logger.exception('Failed to publish commerce data for [%s] to LMS.', course_id)

        return error_message

    def _parse_error(self, response, default_error_message):
        """When validation errors occur during publication, the LMS is expected
         to return an error message.

        Arguments:
            response (Response): A 'Response' object which contains json error message.
            default_error_message (str) : default error message in case of exception.

        Returns:
            string: Returns the error message extracted from response.content
            along with default message. If no message is available in response
            then default message will be return.

        """
        message = None
        try:
            data = response.json()
            if isinstance(data, basestring):
                message = data
            elif isinstance(data, dict) and len(data) > 0:
                message = data.values()[0]
            if isinstance(message, list):
                message = message[0]
        except Exception:  # pylint: disable=broad-except
            pass

        if message:
            return ' '.join([default_error_message, message])
        else:
            return default_error_message
