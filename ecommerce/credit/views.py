

import logging

from dateutil.parser import parse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from oscar.core.loading import get_model
from slumber.exceptions import SlumberHttpBaseException

from ecommerce.courses.models import Course
from ecommerce.extensions.analytics.utils import prepare_analytics_data
from ecommerce.extensions.offer.utils import format_benefit_value
from ecommerce.extensions.partner.shortcuts import get_partner_for_site

logger = logging.getLogger(__name__)
Voucher = get_model('voucher', 'Voucher')


class Checkout(TemplateView):
    """Checkout page that describes the product the user is buying
    and displays the data of the institution offering credit.
    """
    template_name = 'edx/credit/checkout.html'
    CREDIT_MODE = 'credit'

    def get_context_data(self, **kwargs):
        context = super(Checkout, self).get_context_data(**kwargs)

        course = get_object_or_404(Course, id=kwargs.get('course_id'))
        context['course'] = course

        deadline = self._check_credit_eligibility(self.request.user, kwargs.get('course_id'))
        if not deadline:
            context.update({
                'error': _('An error has occurred. We could not confirm that you are eligible for course credit. '
                           'Try the transaction again.')
            })
            return context

        partner = get_partner_for_site(self.request)
        strategy = self.request.strategy
        # Audit seats do not have a `certificate_type` attribute, so
        # we use getattr to avoid an exception.
        credit_seats = []

        for seat in course.seat_products:
            if getattr(seat.attr, 'certificate_type', None) != self.CREDIT_MODE:
                continue

            purchase_info = strategy.fetch_for_product(seat)
            if purchase_info.availability.is_available_to_buy and seat.stockrecords.filter(partner=partner).exists():
                credit_seats.append(seat)

        if not credit_seats:
            msg = _(
                'Credit is not currently available for "{course_name}". If you are currently enrolled in the '
                'course, please try again after all grading is complete. If you need additional assistance, '
                'please contact the {site_name} Support Team.'
            ).format(
                course_name=course.name,
                site_name=self.request.site.name
            )

            context.update({'error': msg})
            return context

        providers = self._get_providers_detail(credit_seats)
        if not providers:
            context.update({
                'error': _('An error has occurred. We could not confirm that the institution you selected offers this '
                           'course credit. Try the transaction again.')
            })
            return context

        context.update({
            'analytics_data': prepare_analytics_data(
                self.request.user,
                self.request.site.siteconfiguration.segment_key,
            ),
            'course': course,
            'deadline': deadline,
            'providers': providers,
        })

        return context

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
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
            credit_api_client = self.request.site.siteconfiguration.credit_api_client
            eligibilities = credit_api_client.eligibility.get(username=user.username, course_key=course_key)
            if not eligibilities:
                return None

            # currently we have only one eligibility for all providers
            return parse(eligibilities[0].get('deadline'))

        except SlumberHttpBaseException:
            logging.exception(
                'Credit API request failed to get eligibility for user [%s] for course [%s].',
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
        code = self.request.GET.get('code')
        if code:
            voucher = Voucher.objects.get(code=code)
            discount_type = voucher.benefit.type
            discount_value = voucher.benefit.value

        providers = self._get_providers_from_lms(credit_seats)
        if not providers:
            return None

        providers_dict = {}
        for provider in providers:
            providers_dict[provider['id']] = provider

        partner = get_partner_for_site(self.request)
        for seat in credit_seats:
            stockrecord = seat.stockrecords.filter(partner=partner).first()
            new_price = None
            discount = None
            if code:
                discount = format_benefit_value(voucher.benefit)
                if discount_type == 'Percentage':
                    new_price = stockrecord.price_excl_tax - (stockrecord.price_excl_tax * (discount_value / 100))
                else:
                    new_price = stockrecord.price_excl_tax - discount_value
                new_price = '{0:.2f}'.format(new_price)
            providers_dict[seat.attr.credit_provider].update({
                'price': stockrecord.price_excl_tax,
                'sku': stockrecord.partner_sku,
                'credit_hours': seat.attr.credit_hours,
                'discount': discount,
                'new_price': new_price
            })

        return list(providers_dict.values())

    def _get_providers_from_lms(self, credit_seats):
        """ Helper method for getting provider info from LMS.

        Arguments:
            credit_seats (Products): List of credit_seats objects.

        Returns:
            Response from LMS as json, containing list of providers.
        """

        provider_ids = ",".join([seat.attr.credit_provider for seat in credit_seats if seat.attr.credit_provider])

        try:
            credit_api_client = self.request.site.siteconfiguration.credit_api_client
            return credit_api_client.providers.get(provider_ids=provider_ids)
        except SlumberHttpBaseException:
            logger.exception('An error occurred while retrieving credit provider details.')
            return None
