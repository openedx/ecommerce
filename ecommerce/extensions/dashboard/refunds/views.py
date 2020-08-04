

from django.views.generic import DetailView, ListView
from oscar.core.loading import get_class, get_model
from oscar.views import sort_queryset

from ecommerce.extensions.dashboard.views import FilterFieldsMixin

Refund = get_model('refund', 'Refund')
RefundSearchForm = get_class('dashboard.refunds.forms', 'RefundSearchForm')


class RefundListView(FilterFieldsMixin, ListView):
    """ Dashboard view to list refunds. """
    model = Refund
    context_object_name = 'refunds'
    template_name = 'oscar/dashboard/refunds/refund_list.html'
    paginate_by = 25
    form_class = RefundSearchForm
    form = None

    def get_filter_fields(self):
        fields = super(RefundListView, self).get_filter_fields()
        fields.update({
            'status': {
                'query_filter': 'status__in',
                'exposed': True,
            }
        })
        return fields

    def get_queryset(self):
        queryset = super(RefundListView, self).get_queryset()
        queryset = queryset.prefetch_related('lines')
        queryset = sort_queryset(queryset, self.request, ['id', 'created'], 'id')

        self.form = self.form_class(self.request.GET)
        if self.form.is_valid():
            for field, value in self.form.cleaned_data.items():
                if value:
                    # Check if the field has a custom query filter setup.
                    # If not, use a standard Django equals/match filter.
                    _filter = self.get_filter_fields().get(field, {}).get('query_filter', field)
                    queryset = queryset.filter(**{_filter: value})

        return queryset

    def get_context_data(self, **kwargs):
        context = super(RefundListView, self).get_context_data(**kwargs)
        context['form'] = self.form
        return context


class RefundDetailView(DetailView):
    model = Refund
    context_object_name = 'refund'
    template_name = 'oscar/dashboard/refunds/refund_detail.html'
