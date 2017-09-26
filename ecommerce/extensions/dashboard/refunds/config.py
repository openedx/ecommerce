from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class RefundsDashboardConfig(AppConfig):
    label = 'refunds_dashboard'
    name = 'ecommerce.extensions.dashboard.refunds'
    verbose_name = _('Refunds Dashboard')
