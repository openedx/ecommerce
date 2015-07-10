import json
import logging

from django.conf import settings
import requests

logger = logging.getLogger(__name__)


class LMSPublisher(object):
    # TODO Test this and update SKU generation
    def mode_for_seat(self, seat):
        if seat.attr.certificate_type == 'professional' and not seat.attr.id_verification_required:
            return 'no-id-professional'
        return seat.attr.certificate_type

    def serialize_seat_for_commerce_api(self, seat):
        """ Serializes a course seat product to a dict that can be further serialized to JSON. """
        stock_record = seat.stockrecords.first()
        return {
            'name': self.mode_for_seat(seat),
            'currency': stock_record.price_currency,
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'expires': seat.expires.isoformat() if seat.expires else None,
        }

    def publish(self, course):
        """ Publish course commerce data to LMS.

        Uses the Commerce API to publish course modes, prices, and SKUs to LMS.

        Args:
            course (Course): Course to be published.

        Returns:
            True, if publish operation succeeded; otherwise, False.
        """

        if not settings.COMMERCE_API_URL:
            logger.error('COMMERCE_API_URL is not set. Commerce data will not be published!')
            return

        modes = [self.serialize_seat_for_commerce_api(seat) for seat in course.seat_products]
        course_id = course.id
        data = {
            'id': course_id,
            'modes': modes
        }

        url = '{}/courses/{}/'.format(settings.COMMERCE_API_URL.rstrip('/'), course_id)
        timeout = settings.COMMERCE_API_TIMEOUT

        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        try:
            response = requests.put(url, data=json.dumps(data), headers=headers, timeout=timeout)
            status_code = response.status_code
            if status_code in (200, 201):
                logger.info(u'Successfully published commerce data for [%s].', course_id)
                return True
            else:
                logger.error(u'Failed to publish commerce data for [%s] to LMS. Status was [%d]. Body was [%s].',
                             course_id, status_code, response.content)
        except Exception:  # pylint: disable=broad-except
            logger.exception(u'Failed to publish commerce data for [%s] to LMS.', course_id)

        return False
