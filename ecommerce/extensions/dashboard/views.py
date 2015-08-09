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
