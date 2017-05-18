import os
from os.path import dirname, join

from dotenv import load_dotenv

from e2e.utils import str2bool

# Load environment variables from an external file. Existing values will take precedence. The variables will be read
# later to configure the tests. See https://github.com/theskumar/python-dotenv.
dotenv_path = os.environ.get('DOTENV_PATH', join(dirname(__file__), '.env'))
load_dotenv(dotenv_path)

OAUTH_ACCESS_TOKEN_URL = os.environ.get('OAUTH_ACCESS_TOKEN_URL')
OAUTH_CLIENT_ID = os.environ.get('OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = os.environ.get('OAUTH_CLIENT_SECRET')

if not all([OAUTH_ACCESS_TOKEN_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET]):
    raise RuntimeError('Valid OAuth details must be provided.')

HONOR_COURSE_ID = os.environ.get('HONOR_COURSE_ID')
VERIFIED_COURSE_ID = os.environ.get('VERIFIED_COURSE_ID')
if not all([HONOR_COURSE_ID, VERIFIED_COURSE_ID]):
    raise RuntimeError('IDs for courses with honor and verified modes are required.')

PROFESSIONAL_COURSE_ID = os.environ.get('PROFESSIONAL_COURSE_ID')

try:
    ECOMMERCE_URL_ROOT = os.environ.get('ECOMMERCE_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('A valid URL root for the E-Commerce Service is required.')

ECOMMERCE_API_URL = os.environ.get('ECOMMERCE_API_URL', ECOMMERCE_URL_ROOT + '/api/v2')
MAX_COMPLETION_RETRIES = int(os.environ.get('MAX_COMPLETION_RETRIES', 3))

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

ENABLE_SSO_TESTS = str2bool(os.environ.get('ENABLE_SSO_TESTS', True))
LMS_USERNAME = os.environ.get('LMS_USERNAME')
LMS_EMAIL = os.environ.get('LMS_EMAIL')
LMS_PASSWORD = os.environ.get('LMS_PASSWORD')
LMS_AUTO_AUTH = str2bool(os.environ.get('LMS_AUTO_AUTH', False))
LMS_HTTPS = str2bool(os.environ.get('LMS_HTTPS', True))
ENROLLMENT_API_URL = os.environ.get('ENROLLMENT_API_URL', LMS_URL_ROOT + '/api/enrollment/v1')
BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD')

if ENABLE_SSO_TESTS and not all([LMS_URL_ROOT, LMS_USERNAME, LMS_PASSWORD]):
    raise RuntimeError('LMS settings are required to run single sign-on tests.')

ENABLE_COUPON_ADMIN_TESTS = str2bool(os.environ.get('ENABLE_COUPON_ADMIN_TESTS', False))

BULK_PURCHASE_SKU = os.environ.get('BULK_PURCHASE_SKU')
