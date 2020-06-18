

import os
from os.path import dirname, join

from dotenv import load_dotenv

# Load environment variables from an external file. Existing values will take precedence. The variables will be read
# later to configure the tests. See https://github.com/theskumar/python-dotenv.
dotenv_path = os.environ.get('DOTENV_PATH', join(dirname(__file__), '.env'))
load_dotenv(dotenv_path)

OAUTH_ACCESS_TOKEN_URL = os.environ.get('OAUTH_ACCESS_TOKEN_URL')
OAUTH_CLIENT_ID = os.environ.get('OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = os.environ.get('OAUTH_CLIENT_SECRET')

if not all([OAUTH_ACCESS_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET]):
    raise RuntimeError('Valid OAuth details must be provided.')

try:
    ECOMMERCE_URL_ROOT = os.environ.get('ECOMMERCE_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('A valid URL root for the E-Commerce Service is required.')

ECOMMERCE_API_URL = os.environ.get('ECOMMERCE_API_URL', ECOMMERCE_URL_ROOT + '/api/v2')
ECOMMERCE_TEST_WEB_SECURITY = os.environ.get('ECOMMERCE_TEST_WEB_SECURITY')

PAYPAL_EMAIL = os.environ.get('PAYPAL_EMAIL')
PAYPAL_PASSWORD = os.environ.get('PAYPAL_PASSWORD')
if not all([PAYPAL_EMAIL, PAYPAL_PASSWORD]):
    raise RuntimeError('PayPal credentials are required to fully test payment.')

try:
    MARKETING_URL_ROOT = os.environ.get('MARKETING_URL_ROOT').strip('/')
except AttributeError:
    MARKETING_URL_ROOT = None

try:
    LMS_URL_ROOT = os.environ.get('LMS_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('A valid LMS URL root is required.')

try:
    DISCOVERY_API_URL_ROOT = os.environ.get('DISCOVERY_API_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('Discovery API URL root is required.')

LMS_USERNAME = os.environ.get('LMS_USERNAME')
LMS_EMAIL = os.environ.get('LMS_EMAIL')
LMS_PASSWORD = os.environ.get('LMS_PASSWORD')
ENROLLMENT_API_URL = os.environ.get('ENROLLMENT_API_URL', LMS_URL_ROOT + '/api/enrollment/v1')
BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD')
HUBSPOT_FORMS_API_URI = os.environ.get('HUBSPOT_FORMS_API_URI')
HUBSPOT_PORTAL_ID = os.environ.get('HUBSPOT_PORTAL_ID')
HUBSPOT_SALES_LEAD_FORM_GUID = os.environ.get('HUBSPOT_SALES_LEAD_FORM_GUID')
