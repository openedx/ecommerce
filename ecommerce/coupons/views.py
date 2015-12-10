from django.views.generic import TemplateView
from ecommerce.core.views import StaffOnlyMixin


class CouponAppView(StaffOnlyMixin, TemplateView):
    template_name = 'coupons/coupon_app.html'
