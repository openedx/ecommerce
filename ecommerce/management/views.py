

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from ecommerce.management.utils import FulfillFrozenBaskets, refund_basket_transactions

logger = logging.getLogger(__name__)


class ManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'management/index.html'

    def test_func(self):
        return self.request.user.is_staff

    def _parse_basket_ids(self, s):
        basket_ids = []

        for basket_id in s.split(','):
            basket_id = int(basket_id.strip())
            basket_ids.append(basket_id)

        return basket_ids

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        action = request.POST.get('action')

        if action:
            logger.info('User [%s] executed action [%s] on the management view.', request.user, action)

        if action == 'refund_basket_transactions':
            basket_ids = self._parse_basket_ids(request.POST.get('basket_ids'))
            success_count, failure_count = refund_basket_transactions(request.site, basket_ids)
            msg = 'Finished refunding basket transactions. [{success_count}] transactions were successfully refunded.' \
                  ' [{failure_count}] attempts failed.'.format(success_count=success_count,
                                                               failure_count=failure_count)
            messages.add_message(request, messages.INFO, msg)
        elif action == 'fulfill':
            basket_ids = self._parse_basket_ids(request.POST.get('basket_ids'))
            for basket_id in basket_ids:
                fulfilled = FulfillFrozenBaskets().fulfill_basket(basket_id=basket_id, site=request.site)
                if fulfilled:
                    logger.info('Fulfilled basket [%s].', basket_id)
                else:
                    logger.info('Unable to fulfill basket [%d]', basket_id)
        else:
            messages.add_message(request, messages.ERROR,
                                 _('{action} is not a valid action.').format(action=action))

        return self.get(request)
