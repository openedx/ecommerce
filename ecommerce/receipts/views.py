from django.views.generic import TemplateView


class ReceiptsView(TemplateView):
    template_name = 'receipt/receipt.html'

    def get_context_data(self, **kwargs):
        context = super(ReceiptsView, self).get_context_data(**kwargs)
        return context
