from collections import OrderedDict
import json
import logging

from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from edx_rest_api_client.client import EdxRestApiClient
from slumber.exceptions import SlumberHttpBaseException
import waffle

from ecommerce.courses.models import Course
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.settings import get_lms_url

logger = logging.getLogger(__name__)


class Checkout(TemplateView):
    """Checkout page that describes the product the user is buying
    and displays the data of the institution offering credit.
    """
    template_name = 'edx/credit/checkout.html'
    CREDIT_MODE = 'credit'

    def get_context_data(self, **kwargs):
        context = super(Checkout, self).get_context_data(**kwargs)

        course = get_object_or_404(Course, id=kwargs.get('course_id'))

        deadline = self._check_credit_eligibility(self.request.user, kwargs.get('course_id'))
        if not deadline:
            return {
                'error': _(u'An error has occurred. We could not confirm that you are eligible for course credit. '
                           u'Try the transaction again.')
            }

        partner = get_partner_for_site(self.request)
        # Audit seats do not have a `certificate_type` attribute, so
        # we use getattr to avoid an exception.
        credit_seats = [
            seat for seat in course.seat_products
            if getattr(seat.attr, 'certificate_type', None) == self.CREDIT_MODE and
            seat.stockrecords.filter(partner=partner).exists()
        ]

        if not credit_seats:
            return {
                'error': _(u'No credit seat is available for this course.')
            }

        providers = self._get_providers_detail(credit_seats)
        if not providers:
            return {
                'error': _(u'An error has occurred. We could not confirm that the institution you selected offers this '
                           u'course credit. Try the transaction again.')
            }

        # Make button text for each processor which will be shown to user.
        processors_dict = OrderedDict()
        for path in settings.PAYMENT_PROCESSORS:
            processor_class = get_processor_class(path)
            if not processor_class.is_enabled():
                continue
            processor = processor_class.NAME.lower()
            if processor == 'cybersource':
                processors_dict[processor] = 'Checkout'
            elif processor == 'paypal':
                processors_dict[processor] = 'Checkout with PayPal'
            else:
                processors_dict[processor] = 'Checkout with {}'.format(processor)
        if len(processors_dict) == 0:
            context.update({
                'error': _(
                    u'All payment options are currently unavailable. Try the transaction again in a few minutes.'
                )
            })

        context.update({
            'course': course,
            'payment_processors': processors_dict,
            'deadline': deadline,
            'providers': providers,
            'analytics_data': prepare_analytics_data(course.id, self.request.user)
        })

        return context

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        """Get method for checkout page."""
        if not waffle.switch_is_active('ENABLE_CREDIT_APP'):
            raise Http404

        return super(Checkout, self).get(request, args, **kwargs)

    def _check_credit_eligibility(self, user, course_key):
        """ Check that the user is eligible for credit.

        Arguments:
            user(User): User object for which checking the eligibility.
            course_key(string): The course identifier.

        Returns:
            Eligibility deadline date or None if user is not eligible.
        """
        try:
            eligibilities = self.credit_api_client.eligibility.get(username=user.username, course_key=course_key)
            if not eligibilities:
                return None

            # currently we have only one eligibility for all providers
            return parse(eligibilities[0].get('deadline'))

        except SlumberHttpBaseException:
            logging.exception(
                u"Credit API request failed to get eligibility for user [%s] for course [%s].",
                user.username,
                course_key
            )
            return None

    def _get_providers_detail(self, credit_seats):
        """ Get details for the credit providers for the given credit seats.

        Arguments:
            credit_seats (Products[]): List of credit_seats objects.

        Returns:
            A list of dictionaries with provider(s) detail.
        """
        providers = self._get_providers_from_lms(credit_seats)
        if not providers:
            return None

        providers_dict = {}
        for provider in providers:
            providers_dict[provider['id']] = provider

        partner = get_partner_for_site(self.request)
        for seat in credit_seats:
            stockrecord = seat.stockrecords.filter(partner=partner).first()
            providers_dict[seat.attr.credit_provider].update({
                'price': stockrecord.price_excl_tax,
                'sku': stockrecord.partner_sku,
                'credit_hours': seat.attr.credit_hours
            })

        return providers_dict.values()

    def _get_providers_from_lms(self, credit_seats):
        """ Helper method for getting provider info from LMS.

        Arguments:
            credit_seats (Products): List of credit_seats objects.

        Returns:
            Response from LMS as json, containing list of providers.
        """

        provider_ids = ",".join([seat.attr.credit_provider for seat in credit_seats if seat.attr.credit_provider])

        try:
            return self.credit_api_client.providers.get(provider_ids=provider_ids)
        except SlumberHttpBaseException:
            logger.exception(u'An error occurred while retrieving credit provider details.')
            return None

    @cached_property
    def credit_api_client(self):
        """ Returns an instance of the Credit API client. """

        return EdxRestApiClient(
            get_lms_url('api/credit/v1/'),
            oauth_access_token=self.request.user.access_token
        )
