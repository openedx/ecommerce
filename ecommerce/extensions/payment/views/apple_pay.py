

import logging

from django.http import HttpResponse
from django.views import View

logger = logging.getLogger(__name__)


class ApplePayMerchantDomainAssociationView(View):
    def get(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        site_configuration = self.request.site.siteconfiguration
        payment_processor_class = site_configuration.get_client_side_payment_processor_class(self.request)
        payment_processor = payment_processor_class(self.request.site)
        content = payment_processor.apple_pay_merchant_id_domain_association
        status_code = 200

        if not content:
            content = 'Apple Pay is not configured for [{}].'.format(request.site.domain)
            # 501 Not Implemented -- https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.5.2
            status_code = 501
            logger.warning(content)

        return HttpResponse(content, content_type='text/plain', status=status_code)
