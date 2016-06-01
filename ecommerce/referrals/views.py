import csv
from datetime import datetime, timedelta
import logging

from django.http import Http404, HttpResponse
from django.utils.text import slugify
from django.views.generic import View
from oscar.core.loading import get_model
from pytz import UTC

from ecommerce.core.httpauth import basic_http_auth
from ecommerce.referrals.models import Referral

logger = logging.getLogger(__name__)
Refund = get_model('refund', 'Refund')


class ValidationReportCsvView(View):
    """ Download affiliate attribution validation CSV file view. """

    @basic_http_auth
    def get(self, request, affiliate_partner):
        """
        Creates a CSV referral validation report The structure of the CSV looks like this:

           > Order Reference,Transaction Date,Status,Status Note

           > ORDER-0001,01/01/2016 12:00:00,ACCEPTED,
           > ORDER-0002,01/01/2016 15:30:00,ACCEPTED,
           > ORDER-0003,01/01/2016 16:00:00,DECLINED,Order refunded

        Args:
            request (Request): The GET request
            affiliate_partner (str): Affiliate partner for the report

        Returns:
            HttpResponse

        Raises:
            Http404: When a non-staff user tries to download a CSV for an affiliate other than themselves.

        """

        if request.user.username != affiliate_partner and not request.user.is_staff:
            raise Http404('No report available for that affiliate.')

        date_param = request.GET.get('date')
        if date_param:
            as_of_date = datetime.strptime(date_param, "%Y-%m-%d")
        else:
            as_of_date = datetime.utcnow()

        report_date = as_of_date - timedelta(days=request.site.siteconfiguration.order_attribution_period)

        start_period = report_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)
        end_period = report_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=UTC)

        referrals = Referral.objects.select_related('order').prefetch_related('order__refunds').filter(
            affiliate_id=affiliate_partner,
            order__date_placed__range=(start_period, end_period)
        )

        order_info = {}
        for referral in referrals:
            order = referral.order
            is_refunded = order.refunds.count() > 0
            order_info[order.id] = {
                'order_number': order.number,
                'transaction_date': order.date_placed.strftime("%d/%m/%Y %H:%M:%S"),
                'refunded': is_refunded,
                'status_note': 'Order refunded' if is_refunded else '',
            }

        file_name = 'Affiliate attribution validation for {affiliate} {date}'.format(
            affiliate=affiliate_partner,
            date=report_date
        )
        file_name = '{filename}.csv'.format(filename=slugify(file_name))

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={filename}'.format(filename=file_name)

        attribution_field_names = ('Order Reference', 'Transaction Date', 'Status', 'Status Note',)
        csv_writer = csv.writer(response)
        csv_writer.writerow(attribution_field_names)
        for order in order_info.values():
            csv_writer.writerow([
                order['order_number'],
                str(order['transaction_date']),
                "DECLINED" if order['refunded'] else "ACCEPTED",
                order['status_note']
            ])

        return response
