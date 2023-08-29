import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.generic import TemplateView
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from requests.exceptions import HTTPError, Timeout
from rest_framework import status, views
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from ecommerce.extensions.payment.core.sdn import SDNClient, checkSDNFallback
from ecommerce.extensions.payment.models import SDNCheckFailure
from ecommerce.extensions.payment.serializers import SDNCheckFailureSerializer

logger = logging.getLogger(__name__)


class SDNCheckFailureView(views.APIView):
    """
    REST API for SDNCheckFailure class.
    """
    http_method_names = ['post', 'options']
    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated, IsAdminUser)
    serializer_class = SDNCheckFailureSerializer

    def _validate_arguments(self, payload):

        invalid = False
        reasons = []
        # Check for presence of required variables
        for arg in ['full_name', 'username', 'city', 'country', 'sdn_check_response']:
            if not payload.get(arg):
                reason = f'{arg} is missing or blank.'
                reasons.append(reason)
        if reasons:
            invalid = True
            return invalid, reasons

        return invalid, reasons

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        payload = request.data
        invalid, reasons = self._validate_arguments(payload)
        if invalid is True:
            logger.warning(
                'Invalid payload for request user %s against SDNCheckFailureView endpoint. Reasons: %s',
                request.user,
                reasons,
            )
            return JsonResponse(
                {'error': ' '.join(reasons)},
                status=400,
            )

        sdn_check_failure = SDNCheckFailure.objects.create(
            full_name=payload['full_name'],
            username=payload['username'],
            city=payload['city'],
            country=payload['country'],
            site=request.site,
            sdn_check_response=payload['sdn_check_response'],
        )

        # This is the point where we would add the products to the SDNCheckFailure obj.
        # We, however, do not know whether the products themselves are relevant to the flow
        # calling this endpoint. If you wanted to attach products to the failure record, you
        # can use skus handed to this endpoint to filter Products using their stockrecords:
        # Product.objects.filter(stockrecords__partner_sku__in=['C92A142','ABC123'])

        # Return a response
        data = self.serializer_class(sdn_check_failure, context={'request': request}).data
        return JsonResponse(data, status=status.HTTP_201_CREATED)


class SDNFailure(TemplateView):
    """ Display an error page when the SDN check fails at checkout. """
    template_name = 'oscar/checkout/sdn_failure.html'

    def get_context_data(self, **kwargs):
        context = super(SDNFailure, self).get_context_data(**kwargs)
        context['logout_url'] = self.request.site.siteconfiguration.build_lms_url('/logout')
        return context


class SDNCheckView(views.APIView):
    """
    View for external services to use to run SDN checks against.

    While this endpoint uses a lot of logic from sdn.py, this endpoint is
    not called during a normal checkout flow (as of 6/8/2023).
    """
    http_method_names = ['post', 'options']
    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated, IsAdminUser)

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
        json_data = {
            'hit_count': hit_count,
            'sdn_response': response,
        }
        return JsonResponse(json_data, status=200)
