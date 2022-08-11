from django.conf import settings
from oscar.core.loading import get_model

from ecommerce.courses.constants import CertificateType
from ecommerce.enterprise.utils import get_enterprise_customer, get_enterprise_id_for_current_request_user_from_jwt

Product = get_model('catalogue', 'Product')
Order = get_model('order', 'Order')


def get_executive_education_2u_product(partner, sku):
    """
    Return a Paid 2U Executive Education product for the sku if it exists.
    """

    product = Product.objects.filter(
        stockrecords__partner=partner, stockrecords__partner_sku=sku
    ).first()

    if product:
        certificate_type = getattr(product.attr, 'certificate_type', '')

        if certificate_type == CertificateType.PAID_EXECUTIVE_EDUCATION:
            return product

    return None


def get_previous_order_for_user(user, product):
    # TODO: figure out if users can place orders multiple times
    return Order.objects.filter(user=user, lines__product=product).first()


def get_learner_portal_url(request):
    enterprise_id = get_enterprise_id_for_current_request_user_from_jwt()
    enterprise_customer = get_enterprise_customer(request.site, enterprise_id)
    slug = enterprise_customer['slug']

    return '{scheme}://{hostname}/{slug}'.format(
        scheme=request.scheme,
        hostname=settings.ENTERPRISE_LEARNER_PORTAL_HOSTNAME,
        slug=slug,
    )
