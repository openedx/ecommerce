from __future__ import absolute_import

from oscar.apps.dashboard.orders.forms import OrderSearchForm as CoreOrderSearchForm

from ecommerce.extensions.dashboard.forms import UserFormMixin


class OrderSearchForm(UserFormMixin, CoreOrderSearchForm):
    """ Order Search Form. """
