from django.conf.urls import url
from django.utils.translation import gettext_lazy as _
from oscar.core.application import OscarDashboardConfig
from oscar.core.loading import get_class


class RefundsDashboardConfig(OscarDashboardConfig):

    label = 'refunds_dashboard'

    name = 'ecommerce.extensions.dashboard.refunds'

    verbose_name = _('Refunds Dashboard')

    default_permissions = ['is_staff', ]

    permissions_map = {
        'refunds-list': (['is_staff'], ['partner.dashboard_access']),
        'refunds-detail': (['is_staff'], ['partner.dashboard_access']),
    }

    # pylint: disable=attribute-defined-outside-init
    def ready(self):
        super().ready()
        self.refund_list_view = get_class('dashboard.refunds.views', 'RefundListView')
        self.refund_detail_view = get_class('dashboard.refunds.views', 'RefundDetailView')

    def get_urls(self):
        urls = [
            url(r'^$', self.refund_list_view.as_view(), name='refunds-list'),
            url(r'^(?P<pk>[\d]+)/$', self.refund_detail_view.as_view(), name='refunds-detail'),
        ]
        return self.post_process_urls(urls)
