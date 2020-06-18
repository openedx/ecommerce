

import requests

from e2e.config import ECOMMERCE_TEST_WEB_SECURITY
from e2e.helpers import EcommerceHelpers

import pytest  # isort:skip


@pytest.mark.skipif(not ECOMMERCE_TEST_WEB_SECURITY, reason='security testing disabled')
class TestWAF:
    """
    Make some simple attacks against the E-Commerce server to test that we have a general WAF (web
    application firewall) in place. These services prevent some common web attacks in a generic way.

    These are only run if specifically requested, since otherwise we'd get noisy failures for local
    servers that obviously aren't going to be running a WAF.
    """

    def setup_method(self):
        # The specific URL doesn't matter. We just want something that doesn't 404 on us
        self.url = EcommerceHelpers.build_url('dashboard/')  # pylint: disable=attribute-defined-outside-init

    def assert_denial(self, response):
        # We only want to consider 4XX statuses -- 5XX isn't expected as a security denial response
        code = response.status_code
        assert 400 <= code < 500, 'Unexpected status code {0}'.format(code)

    def request(self, method='GET', **kwargs):
        # Disallow redirects because otherwise we might see 401 if not logged in, etc.
        # The errors we expect to see will be immediate.
        return requests.request(method, self.url, allow_redirects=False, **kwargs)

    def test_sanity_check(self):
        """
        Make sure that the URL we request in the other tests actually does normally work.
        """
        response = self.request()
        response.raise_for_status()

    def test_xst(self):
        """
        Checks if simple cross site tracing attacks are stopped.
        This is a trivial enough attack that some HTTP servers stop this directly.
        https://www.owasp.org/index.php/Test_HTTP_Methods_(OTG-CONFIG-006)
        """
        response = self.request('TRACE')
        self.assert_denial(response)

    def test_reflected_xss(self):
        """
        Checks if simple reflected cross site scripting attacks are stopped.
        https://www.owasp.org/index.php/Testing_for_Reflected_Cross_site_scripting_(OTG-INPVAL-001)
        """
        response = self.request(params={'id': '<script>alert()</script>'})
        self.assert_denial(response)

    def test_sql_injection(self):
        """
        Checks if simple SQL injection attacks are stopped.
        https://www.owasp.org/index.php/Testing_for_SQL_Injection_(OTG-INPVAL-005)
        """
        response = self.request(params={'id': '10 OR 1=1'})
        self.assert_denial(response)
