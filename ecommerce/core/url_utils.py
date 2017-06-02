import warnings

from threadlocals.threadlocals import get_current_request

from ecommerce.core.exceptions import MissingRequestError


def _get_site_configuration():
    """ Retrieve the SiteConfiguration from the current request from the global thread.

    Notes:
        This is a stopgap. Do NOT use this with any expectation that it will remain in place.
        This function WILL be removed.
    """
    warnings.warn('Usage of _get_site_configuration and django-threadlocals is deprecated. '
                  'Use the helper methods on the SiteConfiguration model.', DeprecationWarning)

    request = get_current_request()

    if request:
        return request.site.siteconfiguration

    raise MissingRequestError


def get_ecommerce_url(path=''):
    """
    Returns path joined with the appropriate ecommerce URL root for the current site

    Raises:
        MissingRequestError: If the current ecommerce site is not in threadlocal storage
    """
    warnings.warn('Usage of get_ecommerce_url and django-threadlocals is deprecated. '
                  'Use SiteConfiguration.build_ecommerce_url instead.', DeprecationWarning)

    site_configuration = _get_site_configuration()
    return site_configuration.build_ecommerce_url(path)
