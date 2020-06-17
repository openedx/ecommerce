

from oscar.apps.dashboard.views import *  # pylint: disable=wildcard-import, unused-wildcard-import


class ExtendedIndexView(IndexView):
    def get_stats(self):
        """
        Statistics for the store dashboard.

        To limit the impact this page can have on systems with millions of orders,
        all queries against orders are limited to those placed in the last 24 hours;
        Order's date_placed field is indexed for more efficient queries.
        """
        datetime_24hrs_ago = now() - timedelta(hours=24)

        orders = Order.objects.filter()
        orders_last_day = orders.filter(date_placed__gt=datetime_24hrs_ago)
        paid_orders_last_day = orders.filter(date_placed__gt=datetime_24hrs_ago, total_incl_tax__gt=0)

        stats = {
            'total_orders_last_day': orders_last_day.count(),

            'average_order_costs': orders_last_day.aggregate(
                Avg('total_incl_tax')
            )['total_incl_tax__avg'] or D('0.00'),

            'average_paid_order_costs': paid_orders_last_day.aggregate(
                Avg('total_incl_tax')
            )['total_incl_tax__avg'] or D('0.00'),

            'total_revenue_last_day': orders_last_day.aggregate(
                Sum('total_incl_tax')
            )['total_incl_tax__sum'] or D('0.00'),

            'hourly_report_dict': self.get_hourly_report(orders_last_day, hours=24),
            'total_customers_last_day': User.objects.filter(
                date_joined__gt=datetime_24hrs_ago,
            ).count(),

            'total_products': Product.objects.count(),

            'total_vouchers': self.get_active_vouchers().count(),
        }

        return stats


class FilterFieldsMixin:
    def get_filter_fields(self):
        """ Returns a dictionary of fields with custom filters. """
        return {
            'username': {
                'query_filter': 'user__username__istartswith',
                'exposed': True
            },
            'email': {
                'query_filter': 'user__email__istartswith',
                'exposed': True
            },
        }

    def exposed_fields(self):
        """ Returns the dictionary of fields that will be immediately exposed to the user in the UI. """
        return {field: details for (field, details) in self.get_filter_fields().items() if details['exposed']}

    def get_context_data(self, **kwargs):
        context = super(FilterFieldsMixin, self).get_context_data(**kwargs)
        context['exposed_field_ids'] = ['id_{}'.format(field) for field in self.exposed_fields().keys()]

        return context
