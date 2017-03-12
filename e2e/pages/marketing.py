import requests
from bok_choy.page_object import PageObject

from e2e.config import BASIC_AUTH_PASSWORD, BASIC_AUTH_USERNAME, MARKETING_URL_ROOT


class MarketingCourseAboutPage(PageObject):
    def __init__(self, browser, course_id):
        super(MarketingCourseAboutPage, self).__init__(browser)

        drupal_catalog_url = '{}/api/catalog/v2/courses/{}'.format(MARKETING_URL_ROOT, course_id)
        response = requests.get(drupal_catalog_url)
        data = response.json()

        self.about_page_path = data['course_about_uri']

    def is_browser_on_page(self):
        return self.q(css='.js-enroll-btn').visible

    @property
    def url(self):
        url = '{}/{}'.format(MARKETING_URL_ROOT, self.about_page_path)

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{}:{}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url
