from collections import OrderedDict
import json
import logging

from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
import requests
from requests.exceptions import ConnectionError, Timeout
import waffle

from ecommerce.courses.models import Course
from ecommerce.extensions.payment.helpers import get_processor_class

logger = logging.getLogger(__name__)


class Checkout(TemplateView):
    """Checkout page that describes the product the user is buying
    and displays the data of the institution offering credit.
    """
    template_name = 'edx/credit/checkout.html'
    CREDIT_MODE = 'credit'

    def get_context_data(self, **kwargs):
        context = super(Checkout, self).get_context_data(**kwargs)

        try:
            course = Course.objects.get(id=kwargs.get('course_id'))
        except Course.DoesNotExist:
            raise Http404

        # Make button text for each processor which will be shown to user.
        processors_dict = OrderedDict()
        for path in settings.PAYMENT_PROCESSORS:
            processor = get_processor_class(path).NAME.lower()
            if processor == 'cybersource':
                processors_dict[processor] = 'Checkout'
            elif processor == 'paypal':
                processors_dict[processor] = 'Checkout with PayPal'
            else:
                processors_dict[processor] = 'Checkout with {}'.format(processor)

        credit_seats = [
            seat for seat in course.seat_products
            if getattr(seat.attr, 'certificate_type', '') == self.CREDIT_MODE
        ]
        provider_ids = None
        if credit_seats:
            provider_ids = ",".join([seat.attr.credit_provider for seat in credit_seats if seat.attr.credit_provider])

        context.update({
            'request': self.request,
            'user': self.request.user,
            'course': course,
            'payment_processors': processors_dict,
            'credit_seats': credit_seats,
            'lms_url_root': settings.LMS_URL_ROOT,
            'provider_ids': provider_ids,
            'analytics_data': json.dumps({
                'course': {
                    'courseId': course.id
                },
                'tracking': {
                    'segmentApplicationId': settings.SEGMENT_KEY
                },
                'user': {
                    'username': self.request.user.get_username(),
                    'name': self.request.user.get_full_name(),
                    'email': self.request.user.email
                }
            })
        })

        return context

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.switch_is_active('ENABLE_CREDIT_APP'):
            raise Http404

        is_eligible, deadline = self._check_credit_eligibility(request.user, kwargs.get('course_id'))
        kwargs['is_eligible'] = is_eligible
        kwargs['deadline'] = deadline

        return super(Checkout, self).get(request, args, **kwargs)

    def _check_credit_eligibility(self, user, course_key):
        """Check that the user is eligible for credit.

        Args:
            user(User): User object for which checking the eligibility.
            course_key(str): The course Key
        Returns:
            True if the user is eligible otherwise False
        """
        logger.info("Retrieving credit eligibility for user [%s] and course [%s]", user.username, course_key)

        is_eligible = None
        deadline = None
        params = {'username': user.username, 'course_key': course_key}
        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
        }

        try:
            response = requests.get(
                settings.CREDIT_API_URL, headers=headers, timeout=settings.CREDIT_FULFILLMENT_TIMEOUT, params=params
            )
            if response.status_code == 200:
                eligibilities = response.json()
                valid_eligibility = self._validate_eligibility(course_key, eligibilities)
                if valid_eligibility:
                    is_eligible = True
                    deadline = valid_eligibility['deadline']
                    deadline = parse(deadline)
                    logger.info("User [%s] is eligible for credit for course [%s].", user.username, course_key)
                else:
                    is_eligible = False
                    logger.info("User [%s] is not eligible for course [%s].", user.username, course_key)
            else:
                logger.error("Credit API request failed for user [%s] for course [%s].", user.username, course_key)
        except ConnectionError:
            logger.exception(
                "Credit API request failed due to network error for user [%s] for course [%s].",
                user.username, course_key
            )
        except Timeout:
            logger.exception("Credit API request timeout for user [%s] for course [%s].", user.username, course_key)

        return is_eligible, deadline

    def _validate_eligibility(self, course_key, eligibilities):
        """
        Validate the eligibilities list contains the dict of the given course_key and username.

        Args:
            username(str): username of user.
            course_key(str): course_key for the course.

        Returns:
            A dict of eligibility containing the username and course_key if found else None.
        """
        valid_eligibility = None
        if eligibilities and isinstance(eligibilities, list):
            for eligibility in eligibilities:
                if eligibility['course_key'] == course_key:
                    valid_eligibility = eligibility
                    break

        return valid_eligibility
