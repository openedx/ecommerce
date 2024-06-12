

import json
import logging
from urllib.parse import urljoin

from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from requests.exceptions import HTTPError

from ecommerce.core.constants import ENROLLMENT_CODE_SEAT_TYPES
from ecommerce.courses.constants import CertificateType
from ecommerce.courses.utils import mode_for_product

logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class LMSPublisher:
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

        android_sku = None
        ios_sku = None
        if getattr(seat.attr, 'certificate_type', '') == CertificateType.VERIFIED:
            android_stock_record = StockRecord.objects.filter(
                product__parent=seat.parent, partner_sku__contains='mobile.android').first()
            ios_stock_record = StockRecord.objects.filter(
                product__parent=seat.parent, partner_sku__contains='mobile.ios').first()
            if android_stock_record:
                android_sku = android_stock_record.partner_sku
            if ios_stock_record:
                ios_sku = ios_stock_record.partner_sku

        return {
            'name': mode_for_product(seat),
            'currency': stock_record.price_currency,
            'price': int(stock_record.price),
            'sku': stock_record.partner_sku,
            'bulk_sku': bulk_sku,
            'expires': self.get_seat_expiration(seat),
            'android_sku': android_sku,
            'ios_sku': ios_sku,
        }

    def publish(self, course):
        """ Publish course commerce data to LMS.

        Uses the Commerce API to publish course modes, prices, and SKUs to LMS. Uses
        CreditCourse API endpoints to publish CreditCourse data to LMS when necessary.

        Arguments:
            course (Course): Course to be published.

        Returns:
            None, if publish operation succeeded; otherwise, error message.
        """
        site = course.partner.default_site
        course_id = course.id
        error_message = _('Failed to publish commerce data for {course_id} to LMS.').format(course_id=course_id)

        name = course.name
        verification_deadline = self.get_course_verification_deadline(course)

        # Do not fetch mobile seats to create Course modes. Mobile skus are
        # added to the verified course mode in serialize_seat_for_commerce_api()
        seat_products = course.seat_products.filter(~Q(stockrecords__partner_sku__contains="mobile"))
        modes = [self.serialize_seat_for_commerce_api(seat) for seat in seat_products]

        has_credit = 'credit' in [mode['name'] for mode in modes]
        if has_credit:
            try:
                data = {
                    'course_key': course_id,
                    'enabled': True
                }
                client = site.siteconfiguration.oauth_api_client
                courses_url = urljoin(f"{site.siteconfiguration.credit_api_url}/", f"courses/{course_id}/")
                response = client.put(courses_url, json=data)
                response.raise_for_status()
                logger.info('Successfully published CreditCourse for [%s] to LMS.', course_id)
            except HTTPError as e:
                logger.exception(
                    'Failed to publish CreditCourse for [%s] to LMS. Error was %s.', course_id, e
                )
                return error_message
            except:  # pylint: disable=bare-except
                logger.exception('Failed to publish CreditCourse for [%s] to LMS.', course_id)
                return error_message

        try:
            data = {
                'id': course_id,
                'name': name,
                'verification_deadline': verification_deadline,
                'modes': modes,
            }

            api_client = site.siteconfiguration.oauth_api_client
            commerce_url = urljoin(f"{site.siteconfiguration.commerce_api_url}/", f"courses/{course_id}/")
            response = api_client.put(commerce_url, json=data)
            response.raise_for_status()
            logger.info('Successfully published commerce data for [%s].', course_id)
            return None
        except HTTPError as e:  # pylint: disable=bare-except
            logger.exception(
                'Failed to publish commerce data for [%s] to LMS. Error was %s.', course_id, e
            )
            return self._parse_error(e.response.content, error_message)
        except Exception:  # pylint: disable=broad-except
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
            data = json.loads(response)
            if isinstance(data, str):
                message = data
            elif isinstance(data, dict) and data:
                message = list(data.values())[0]
            if isinstance(message, list):
                message = message[0]
        except Exception:  # pylint: disable=broad-except
            pass

        if message:
            return ' '.join([default_error_message, message])

        return default_error_message
