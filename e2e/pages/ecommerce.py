from bok_choy.page_object import PageObject

from e2e.config import ECOMMERCE_URL_ROOT
from e2e.pages.lms import LMSLoginPage


class EcommerceAppPage(PageObject):  # pylint: disable=abstract-method
    path = None
    server_url = ECOMMERCE_URL_ROOT

    @classmethod
    def build_ecommerce_url(cls, path):
        return '{}/{}'.format(cls.server_url, path)

    @property
    def url(self):
        return self.page_url

    def __init__(self, browser, path=None):
        super(EcommerceAppPage, self).__init__(browser)
        path = path or self.path
        self.page_url = self.build_ecommerce_url(path)


class EcommerceDashboardHomePage(EcommerceAppPage):
    path = 'dashboard'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Dashboard | Oscar')


class EcommerceLoginPage(LMSLoginPage):
    """ Otto login page.

    Although the URL is an Otto URL, this page actually redirects to the LMS login page, hence our inheriting
    that page and it's properties.
    """

    def url(self, course_id=None):  # pylint: disable=arguments-differ,unused-argument
        return EcommerceAppPage.build_ecommerce_url('login')
