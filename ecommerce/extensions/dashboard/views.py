from oscar.apps.dashboard.views import *  # pylint: disable=wildcard-import, unused-wildcard-import


class ExtendedIndexView(IndexView):
    def get_stats(self):
        stats = super(ExtendedIndexView, self).get_stats()

        datetime_24hrs_ago = now() - timedelta(hours=24)
        orders = Order.objects.filter()
        paid_orders_last_day = orders.filter(date_placed__gt=datetime_24hrs_ago, total_incl_tax__gt=0)

        stats['average_paid_order_costs'] = paid_orders_last_day.aggregate(
            Avg('total_incl_tax')
        )['total_incl_tax__avg'] or D('0.00')

        return stats


class FilterFieldsMixin(object):
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
        return {field: details for (field, details) in self.get_filter_fields().iteritems() if details['exposed']}

    def get_context_data(self, **kwargs):
        context = super(FilterFieldsMixin, self).get_context_data(**kwargs)
        context['exposed_field_ids'] = ['id_{}'.format(field) for field in self.exposed_fields().keys()]

        return context
