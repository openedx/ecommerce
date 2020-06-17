

import csv
import logging

from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View
from oscar.core.loading import get_model

from ecommerce.core.views import StaffOnlyMixin
from ecommerce.extensions.voucher.utils import generate_coupon_report

logger = logging.getLogger(__name__)

Benefit = get_model('offer', 'Benefit')
CouponVouchers = get_model('voucher', 'CouponVouchers')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class CouponReportCSVView(StaffOnlyMixin, View):
    """Generates coupon report and returns it in CSV format."""

    def get(self, request, coupon_id):  # pylint: disable=unused-argument
        """
        Generate coupon report for vouchers associated with the coupon.
        """
        coupon = Product.objects.get(id=coupon_id)
        filename = _("Coupon Report for {coupon_name}").format(coupon_name=str(coupon))
        coupons_vouchers = CouponVouchers.objects.filter(coupon=coupon)

        filename = "{}.csv".format(slugify(filename))

        try:
            field_names, rows = generate_coupon_report(coupons_vouchers)
        except StockRecord.DoesNotExist:
            logger.exception(u'Failed to find StockRecord for Coupon [%d].', coupon.id)
            return HttpResponse(_('Failed to find a matching stock record for coupon, report download canceled.'),
                                status=404)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)

        writer = csv.DictWriter(response, fieldnames=field_names)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        return response
