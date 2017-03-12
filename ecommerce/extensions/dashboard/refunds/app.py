from django.conf.urls import url
from oscar.core.application import Application
from oscar.core.loading import get_class


class RefundsDashboardApplication(Application):
    name = 'refunds'
    default_permissions = ['is_staff', ]
    permissions_map = {
        'list': (['is_staff'], ['partner.dashboard_access']),
        'detail': (['is_staff'], ['partner.dashboard_access']),
    }

    refund_list_view = get_class('dashboard.refunds.views', 'RefundListView')
    refund_detail_view = get_class('dashboard.refunds.views', 'RefundDetailView')

    def get_urls(self):
        urls = [
            url(r'^$', self.refund_list_view.as_view(), name='list'),
            url(r'^(?P<pk>[\d]+)/$', self.refund_detail_view.as_view(), name='detail'),
        ]
        return self.post_process_urls(urls)


application = RefundsDashboardApplication()
