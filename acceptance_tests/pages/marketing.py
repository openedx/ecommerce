import urllib

from bok_choy.page_object import PageObject

from acceptance_tests.config import MARKETING_URL_ROOT, BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD


class MarketingCourseAboutPage(PageObject):
    def is_browser_on_page(self):
        return self.q(css='.js-enroll-btn').visible

    def _build_url(self, path):
        url = '{}/{}'.format(MARKETING_URL_ROOT, path)

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{}:{}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url

    @property
    def url(self):
        path = 'course/{}'.format(urllib.quote_plus(self.slug))
        return self._build_url(path)

    def __init__(self, browser, slug):
        super(MarketingCourseAboutPage, self).__init__(browser)
        self.slug = slug
