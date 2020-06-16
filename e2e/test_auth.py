

from selenium.common.exceptions import NoSuchElementException

from e2e.config import LMS_URL_ROOT, MARKETING_URL_ROOT
from e2e.helpers import EcommerceHelpers, LmsHelpers

import pytest  # isort:skip


def test_login_and_logout(selenium):
    """ Authenticating with the identity provider (LMS) should authenticate users for the E-Commerce Service.  """

    LmsHelpers.login(selenium)

    # Visit the Otto dashboard to trigger a login
    EcommerceHelpers.visit_dashboard(selenium)

    # Logging out of Otto should redirect the user to the LMS logout page, which redirects
    # to the marketing site (if available) or the LMS homepage.
    EcommerceHelpers.logout(selenium)
    assert selenium.current_url.strip('/') in [MARKETING_URL_ROOT, LMS_URL_ROOT]


def test_provider_logout(selenium):
    """ Logging out of the identity provider should log the user out of the E-Commerce Service. """

    LmsHelpers.login(selenium)

    # Visit the Otto dashboard to trigger a login
    EcommerceHelpers.visit_dashboard(selenium)

    LmsHelpers.logout(selenium)

    # Now that the user has been logged out, navigating to the dashboard should result in the user being
    # redirected to the identity provider's login page. This indicates the user has been logged out of both systems.
    try:
        EcommerceHelpers.visit_dashboard(selenium)
    except NoSuchElementException:
        pass
    else:
        pytest.fail('Logging out of the identity provider should have also logged out of the E-Commerce Service!')


def test_login_redirection(selenium):
    """ If the login process is initiated at the E-Commerce Service, a successful login should return the user to
    the service. """
    # Visit LMS once to perform basic authentication
    selenium.get(LmsHelpers.build_url(''))

    selenium.get(EcommerceHelpers.build_url('dashboard'))
    LmsHelpers.submit_login_form(selenium)
    EcommerceHelpers.assert_on_dashboard(selenium)
