

from ecommerce.core.url_utils import get_lms_dashboard_url, get_lms_url


def core(request):
    site = request.site
    site_configuration = site.siteconfiguration

    return {
        'lms_base_url': get_lms_url(),
        'lms_dashboard_url': get_lms_dashboard_url(),
        'platform_name': site.name,
        'support_url': site_configuration.payment_support_url,
        'optimizely_snippet_src': site_configuration.optimizely_snippet_src,
    }
