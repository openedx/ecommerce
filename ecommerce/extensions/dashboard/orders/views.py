

from django.contrib import messages
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from oscar.apps.dashboard.orders.views import OrderDetailView as CoreOrderDetailView
from oscar.apps.dashboard.orders.views import OrderListView as CoreOrderListView
from oscar.core.loading import get_model

from ecommerce.extensions.dashboard.views import FilterFieldsMixin

Order = get_model('order', 'Order')
Partner = get_model('partner', 'Partner')
Refund = get_model('refund', 'Refund')


def queryset_orders_for_user(user):  # pylint: disable=unused-argument
    """
    Returns a queryset of all orders that a user is allowed to access.
    A staff user may access all orders.
    To allow access to an order for a non-staff user, at least one line's
    partner has to have the user in the partner's list.

    This customization removes the selection of the related address data, as it drastically decreases
    query response time. Support for non-staff users is also removed.
    """
    return Order._default_manager.select_related('user').prefetch_related('lines')  # pylint: disable=protected-access


class OrderListView(FilterFieldsMixin, CoreOrderListView):
    base_queryset = None
    form = None

    def dispatch(self, request, *args, **kwargs):
        # NOTE: This method is overridden so that we can use our override of `queryset_orders_for_user`.

        # base_queryset is equal to all orders the user is allowed to access
        self.base_queryset = queryset_orders_for_user(request.user).order_by('-date_placed')

        # Bypass the CoreOrderListView.dispatch()
        return super(CoreOrderListView, self).dispatch(request, *args, **kwargs)  # pylint: disable=bad-super-call

    def get_queryset(self):
        queryset = super(OrderListView, self).get_queryset()

        # Note (CCB): We set self.form here because the super method does not always pass request.GET
        # to the form constructor. This results in the form not being populated when re-rendered.
        self.form = self.form_class(self.request.GET)
        if self.form.is_valid():
            for field, value in self.form.cleaned_data.items():
                if value:
                    _filter = self.get_filter_fields().get(field)

                    if _filter:
                        queryset = queryset.filter(**{_filter['query_filter']: value})

        return queryset


class OrderDetailView(CoreOrderDetailView):
    line_actions = ('change_line_statuses', 'create_shipping_event', 'create_payment_event', 'create_refund')

    def create_refund(self, request, order, lines, _quantities):  # pylint: disable=unused-argument
        refund = Refund.create_with_lines(order, lines)

        if refund:
            data = {
                'link_start': '<a href="{}" target="_blank">'.format(
                    reverse('dashboard:refunds-detail', kwargs={'pk': refund.pk})),
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
