

from django.contrib.auth.decorators import login_required
from django.urls import path
from oscar.apps.basket import apps
from oscar.core.loading import get_class


class BasketConfig(apps.BasketConfig):
    name = 'ecommerce.extensions.basket'

    # pylint: disable=attribute-defined-outside-init
    def ready(self):
        super().ready()
        self.basket_add_items_view = get_class('basket.views', 'BasketAddItemsView')
        self.summary_view = get_class('basket.views', 'BasketSummaryView')

    def get_urls(self):
        urls = [
            path('', login_required(self.summary_view.as_view()), name='summary'),
            path('add/<int:pk>/', self.add_view.as_view(), name='add'),
            path('vouchers/add/', self.add_voucher_view.as_view(), name='vouchers-add'),
            path('vouchers/<int:pk>/remove/', self.remove_voucher_view.as_view(), name='vouchers-remove'),
            path('saved/', login_required(self.saved_view.as_view()), name='saved'),
            path('add/', self.basket_add_items_view.as_view(), name='basket-add'),
        ]
        return self.post_process_urls(urls)
