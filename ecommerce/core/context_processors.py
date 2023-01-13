

from babel.numbers import get_currency_symbol
from django.conf import settings

from ecommerce.core.url_utils import get_favicon_url, get_lms_dashboard_url, get_lms_url, get_logo_url


def core(request):
    site = request.site
    site_configuration = site.siteconfiguration

    return {
        'lms_base_url': get_lms_url(),
        'lms_dashboard_url': get_lms_dashboard_url(),
        'platform_name': site.name,
        'support_url': site_configuration.payment_support_url,
        'logo_url': get_logo_url(),
        'favicon_url': get_favicon_url(),
        'optimizely_snippet_src': site_configuration.optimizely_snippet_src,
    }


def localization(_request):
    defaults = getattr(settings, "COURSE_MODE_DEFAULTS", {})
    default_currency = defaults.get("currency")
    registration_currency = getattr(settings, "PAID_COURSE_REGISTRATION_CURRENCY", None)
    currency_code = registration_currency or default_currency or "USD"

    if not isinstance(currency_code, str):
        raise ValueError(f"Currency code must be a string; currently: {currency_code}")

    return {
        # Note: babel returns code if not found
        # get_currency_symbol("XYZ") => "XYZ"
        "currency_symbol_": get_currency_symbol(currency_code),
        "currency_code_": currency_code,
    }
