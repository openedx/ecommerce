from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from oscar.apps.basket import app
from oscar.core.loading import get_class


class BasketApplication(app.BasketApplication):
    single_item_view = get_class('basket.views', 'BasketSingleItemView')
    summary_view = get_class('basket.views', 'BasketSummaryView')

    def get_urls(self):
        urls = [
            url(r'^$', self.summary_view.as_view(), name='summary'),
            url(r'^add/(?P<pk>\d+)/$', self.add_view.as_view(), name='add'),
            url(r'^vouchers/add/$', self.add_voucher_view.as_view(), name='vouchers-add'),
            url(r'^vouchers/(?P<pk>\d+)/remove/$', self.remove_voucher_view.as_view(), name='vouchers-remove'),
            url(r'^saved/$', login_required(self.saved_view.as_view()), name='saved'),
            url(r'^single-item/$', login_required(self.single_item_view.as_view()), name='single-item'),
        ]
        return self.post_process_urls(urls)


application = BasketApplication()
