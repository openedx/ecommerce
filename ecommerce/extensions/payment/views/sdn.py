import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, View
from requests.exceptions import HTTPError, Timeout

from ecommerce.extensions.payment.core.sdn import SDNClient, checkSDNFallback

logger = logging.getLogger(__name__)


class SDNFailure(TemplateView):
    """ Display an error page when the SDN check fails at checkout. """
    template_name = 'oscar/checkout/sdn_failure.html'

    def get_context_data(self, **kwargs):
        context = super(SDNFailure, self).get_context_data(**kwargs)
        context['logout_url'] = self.request.site.siteconfiguration.build_lms_url('/logout')
        return context


class SDNCheckView(View):
    """
    View for external services to use to run SDN checks against.
    
    While this endpoint uses a lot of logic from sdn.py, this endpoint is
    not called during a normal checkout flow (as of 6/8/2023).
    """
    http_method_names = ['post', 'options']

    @method_decorator(login_required)
    def post(self, request):
        """
        Use data provided to check against SDN list.
        
        Return a count of hits.
        """
        payload = request.POST

        # Make sure we have the values needed to carry out the request
        missing_args = []
        for expected_arg in ['lms_user_id', 'name', 'city', 'country']:
            if not payload.get(expected_arg):
                missing_args.append(expected_arg)

        if missing_args:            
            return JsonResponse({
                'missing_args': ', '.join(missing_args)
            }, status=400)

        # Begin the check logic
        lms_user_id = payload.get('lms_user_id')
        name = payload.get('name')
        city = payload.get('city')
        country = payload.get('country')
        sdn_list = payload.get('sdn_list', 'ISN,SDN')  # Set SDN lists to a sane default

        sdn_check = SDNClient(
            api_url=settings.SDN_CHECK_API_URL,
            api_key=settings.SDN_CHECK_API_KEY,
            sdn_list=sdn_list
        )
        try:
            response = sdn_check.search(name, city, country)
        except (HTTPError, Timeout) as e:
            logger.info(
                'SDNCheck: SDN API call received an error: %s. SDNFallback function called for user %s.',
                str(e),
                lms_user_id
            )
            sdn_fallback_hit_count = checkSDNFallback(
                name,
                city,
                country
            )
            response = {'total': sdn_fallback_hit_count}

        hit_count = response['total']
        if hit_count > 0:
            logger.info(
                'SDNCheck Endpoint called for lms user [%s]. It received %d hit(s).',
                lms_user_id,
                hit_count,
            )
        else:
            logger.info(
                'SDNCheck function called for lms user [%s]. It did not receive a hit.',
                lms_user_id,
            )
        return JsonResponse({'hit_count': hit_count}, status=200)
