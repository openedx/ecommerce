import json
import logging

from django.conf import settings
import requests

from ecommerce.courses.utils import mode_for_seat
from ecommerce.settings.base import get_lms_url


logger = logging.getLogger(__name__)


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
        return {
            'name': mode_for_seat(seat),
            'currency': stock_record.price_currency,
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'expires': self.get_seat_expiration(seat),
        }

    def _publish_creditcourse(self, course_id, access_token):
        """Creates or updates a CreditCourse object on the LMS."""
        url = get_lms_url('api/credit/v1/courses/')

        data = {
            'course_key': course_id,
            'enabled': True
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }

        kwargs = {
            'url': url,
            'data': json.dumps(data),
            'headers': headers,
            'timeout': self.timeout
        }
        response = requests.post(**kwargs)
        if response.status_code == 400:
            # The CreditCourse already exists. Try updating it.
            kwargs['url'] += course_id.strip('/') + '/'
            response = requests.put(**kwargs)

        return response

    def publish(self, course, access_token=None):
        """ Publish course commerce data to LMS.

        Uses the Commerce API to publish course modes, prices, and SKUs to LMS. Uses
        CreditCourse API endpoints to publish CreditCourse data to LMS when necessary.

        Arguments:
            course (Course): Course to be published.

        Keyword Arguments:
            access_token (str): Access token used when publishing CreditCourse data to the LMS.

        Returns:
            True, if publish operation succeeded; otherwise, False.
        """

        if not settings.COMMERCE_API_URL:
            error_message = 'COMMERCE_API_URL is not set. Commerce data will not be published!'
            logger.error(error_message)

            return False, error_message

        course_id = course.id
        name = course.name
        verification_deadline = self.get_course_verification_deadline(course)
        modes = [self.serialize_seat_for_commerce_api(seat) for seat in course.seat_products]

        has_credit = 'credit' in [mode['name'] for mode in modes]
        if has_credit:
            if access_token is not None:
                try:
                    response = self._publish_creditcourse(course_id, access_token)
                    if response.status_code in (200, 201):
                        logger.info(u'Successfully published CreditCourse for [%s] to LMS.', course_id)
                    else:
                        logger.error(
                            u'Failed to publish CreditCourse for [%s] to LMS. Status was [%d]. Body was [%s].',
                            course_id,
                            response.status_code,
                            response.content
                        )
                        return False
                except:  # pylint: disable=bare-except
                    logger.exception(u'Failed to publish CreditCourse for [%s] to LMS.', course_id)
                    return False
            else:
                logger.error(
                    u'Unable to publish CreditCourse for [%s] to LMS. No access token available.',
                    course_id
                )
                return False

        data = {
            'id': course_id,
            'name': name,
            'verification_deadline': verification_deadline,
            'modes': modes,
        }

        url = '{}/courses/{}/'.format(settings.COMMERCE_API_URL.rstrip('/'), course_id)
        timeout = settings.COMMERCE_API_TIMEOUT

        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        try:
            response = requests.put(url, data=json.dumps(data), headers=headers, timeout=timeout)
        except Exception as e:  # pylint: disable=broad-except
            error_message = (
                u'Failed to publish commerce data for [{course_id}] to LMS. Error was [{error}]').format(
                    course_id=course_id,
                    error=e.message
            )

            logger.exception(error_message)
            return False, error_message

        status_code = response.status_code
        if status_code in (200, 201):
            success_msg = (
                u'Successfully published commerce data for [{course_id}].').format(
                    course_id=course_id
            )
            logger.info(success_msg)
            return True, success_msg

        try:
            data = json.loads(response.content)
        except Exception:  # pylint: disable=broad-except
            error_message = (
                u'Failed to publish commerce data for [{course_id}] to LMS. Json was invalid.').format(
                    course_id=course_id
            )
            logger.exception(error_message)
            return False, error_message

        error_dict = data.get('id', None)
        if error_dict:
            error_message = error_dict
        else:
            error_message = (
                u"Failed to publish commerce data for [{course_id}] to LMS. "
                u"Status was [{status_code}]. Body was [{response}].").format(
                    course_id=course_id,
                    status_code=status_code,
                    response=response.content
            )
        logger.error(error_message)

        return False, error_message
