from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from oscar.apps.dashboard.orders.views import OrderDetailView as CoreOrderDetailView
from oscar.core.loading import get_model

Refund = get_model('refund', 'Refund')


class OrderDetailView(CoreOrderDetailView):
    line_actions = ('change_line_statuses', 'create_shipping_event', 'create_payment_event', 'create_refund')

    def create_refund(self, request, order, lines, _quantities):  # pylint: disable=unused-argument
        refund = Refund.create_with_lines(order, lines)

        if refund:
            data = {
                'link_start': '<a href="{}" target="_blank">'.format(
                    reverse('dashboard:refunds:detail', kwargs={'pk': refund.pk})),
                'link_end': '</a>',
                'refund_id': refund.pk
            }
            message = _('{link_start}Refund #{refund_id}{link_end} created! '
                        'Click {link_start}here{link_end} to view it.').format(**data)
            messages.success(request, mark_safe(message))
        else:
            message = _('A refund cannot be created for these lines. They may have already been refunded.')
            messages.error(request, message)

        return self.reload_page()
