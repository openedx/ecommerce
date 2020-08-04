

from urllib.parse import urlencode

import requests

from e2e.config import HUBSPOT_FORMS_API_URI, HUBSPOT_PORTAL_ID, HUBSPOT_SALES_LEAD_FORM_GUID

import pytest  # isort:skip


class TestHubSpotFormsApi:
    """
    A quick integration test to determine that HubSpot's Forms API is continuing to work as we would expect. Make a post
    to the API with information like our live system would include. Verify that HubSpot received the info by checking
    response status code which should be a 204.

    Before running please do the following:
    - Make sure there are valid settings for the HubSpot parameters in your .env file. These can be found in the
      edx-internal repo within the edx-remote-config/stage/ecommerce.yml file
    - Connect to ecommerce shell and navigate to e2e folder
    - Comment out the pytest annotation on line 28
    - Run test with 'pytest test_hubspot_forms_submission.py' command
    """

    def assert_response(self, response):
        assert response.status_code == 204

    @pytest.mark.skip(reason='HubSpot Forms integration test intended to be run only as needed')
    def test_hubspot_forms_api(self):
        headers = {"Content-Type": 'application/x-www-form-urlencoded'}
        endpoint = "{}{}/{}?&".format(
            HUBSPOT_FORMS_API_URI, HUBSPOT_PORTAL_ID, HUBSPOT_SALES_LEAD_FORM_GUID)
        data = urlencode({
            'firstname': 'John',
            'lastname': 'Doe',
            'email': 'ecommerce_test_0@example.com',
            'address': '1 Test Street',
            'city': 'Boston',
            'state': 'MA',
            'country': 'United States',
            'company': 'Acme',
            'deal_value': 50,
            'ecommerce_course_name': 'edX Demonstration Course',
            'ecommerce_course_id': 'course-v1:edX+DemoX+Demo_Course',
            'bulk_purchase_quantity': 1
        })

        response = requests.post(url=endpoint, data=data, headers=headers, timeout=1)
        self.assert_response(response)
