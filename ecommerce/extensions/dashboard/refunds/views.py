from django.views.generic import ListView, DetailView

from oscar.core.loading import get_class, get_model
from oscar.views import sort_queryset

Refund = get_model('refund', 'Refund')
RefundSearchForm = get_class('dashboard.refunds.forms', 'RefundSearchForm')


class RefundListView(ListView):
    """ Dashboard view to list refunds. """
    model = Refund
    context_object_name = 'refunds'
    template_name = 'dashboard/refunds/refund_list.html'
    paginate_by = 25
    form_class = RefundSearchForm
    form = None

    def get_queryset(self):
        queryset = super(RefundListView, self).get_queryset()
        queryset = queryset.prefetch_related('lines')
        queryset = sort_queryset(queryset, self.request, ['id'], 'id')

        self.form = self.form_class(self.request.GET)

        if self.form.is_valid():
            for field, value in self.form.cleaned_data.iteritems():
                if value:
                    queryset = queryset.filter(**{field: value})

        return queryset

    def get_context_data(self, **kwargs):
        context = super(RefundListView, self).get_context_data(**kwargs)
        context['form'] = self.form
        return context


class RefundDetailView(DetailView):
    model = Refund
    context_object_name = 'refund'
    template_name = 'dashboard/refunds/refund_detail.html'
