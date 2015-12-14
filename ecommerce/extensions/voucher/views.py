import csv

from django.conf import settings
from django.http import HttpResponse
from django.utils.text import slugify
from django.views.generic import View
from oscar.core.loading import get_model

from ecommerce.extensions.voucher.utils import generate_voucher_report

Benefit = get_model('offer', 'Benefit')
CouponVouchers = get_model('voucher', 'CouponVouchers')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class VoucherReportView(View):
    """Generates voucher report and returns it in CSV format."""

    def get(self, request, coupon_id=None):
        """
        Generate voucher report for vouchers associated with the coupon.
        If no coupon was sent, voucher report will be generated for all created vouchers.
        """

        filename = "Voucher Report for"

        if coupon_id:
            coupon = Product.objects.get(id=coupon_id)
            filename += " {}".format(unicode(coupon))
            coupons_vouchers = CouponVouchers.objects.filter(coupon=coupon)
        else:
            filename += " all vouchers"
            coupons_vouchers = CouponVouchers.objects.all()

        filename = slugify(filename) + '.csv'

        vouchers = []
        for coupon_voucher in coupons_vouchers:
            for voucher in coupon_voucher.vouchers.all():
                voucher.catalogue = voucher.offers.all().first().condition.range.catalog.name
                voucher.discount = unicode(voucher.offers.all().first().benefit.value)
                voucher.benefit_type = voucher.offers.all().first().benefit.type
                currency = StockRecord.objects.get(product=coupon_voucher.coupon).price_currency
                voucher.discount += " %" if voucher.benefit_type == Benefit.PERCENTAGE else " {}".format(currency)
                voucher.URL = '{}/coupons/redeem/?code={}'.format(settings.ECOMMERCE_URL_ROOT, voucher.code)
                vouchers.append(voucher)

        field_names, rows = generate_voucher_report(vouchers)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}'.format(
            filename
        )

        writer = csv.DictWriter(response, fieldnames=field_names)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)

        return response
