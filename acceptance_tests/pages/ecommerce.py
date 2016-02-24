from bok_choy.page_object import PageObject

from acceptance_tests.config import ECOMMERCE_URL_ROOT


class EcommerceAppPage(PageObject):  # pylint: disable=abstract-method
    path = None

    @property
    def url(self):
        return self.page_url

    def __init__(self, browser, path=None):
        super(EcommerceAppPage, self).__init__(browser)
        path = path or self.path
        self.server_url = ECOMMERCE_URL_ROOT
        self.page_url = '{}/{}'.format(self.server_url, path)


class DashboardHomePage(EcommerceAppPage):
    path = 'dashboard'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Dashboard | Oscar')
