import os
from acceptance_tests.utils import str2bool


ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
if ACCESS_TOKEN is None:
    raise RuntimeError('A valid OAuth2 access token is required.')

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
ENABLE_CYBERSOURCE_TESTS = str2bool(os.environ.get('ENABLE_CYBERSOURCE_TESTS', True))
ENABLE_PAYPAL_TESTS = str2bool(os.environ.get('ENABLE_PAYPAL_TESTS', True))
ENABLE_STRIPE_TESTS = str2bool(os.environ.get('ENABLE_STRIPE_TESTS', False))
# END OTTO CONFIGURATION

# MARKETING CONFIGURATION
ENABLE_MARKETING_SITE = str2bool(os.environ.get('ENABLE_MARKETING_SITE', False))

MARKETING_URL_ROOT = os.environ.get('MARKETING_URL_ROOT').strip('/') if ENABLE_MARKETING_SITE else None

# These must correspond to the course IDs provided for each enrollment mode.
VERIFIED_COURSE_SLUG = os.environ.get(
    'VERIFIED_COURSE_SLUG',
    'dracula-stoker-berkeleyx-book-club-uc-berkeleyx-colwri3-6x'
)
PROFESSIONAL_COURSE_SLUG = os.environ.get(
    'PROFESSIONAL_COURSE_SLUG',
    'marketing-non-marketers-ubcx-marketing5501x'
)
# END MARKETING CONFIGURATION

try:
    LMS_URL_ROOT = os.environ.get('LMS_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('A valid LMS URL root is required.')

ENABLE_OAUTH2_TESTS = str2bool(os.environ.get('ENABLE_OAUTH2_TESTS', True))
LMS_USERNAME = os.environ.get('LMS_USERNAME')
LMS_EMAIL = os.environ.get('LMS_EMAIL')
LMS_PASSWORD = os.environ.get('LMS_PASSWORD')
LMS_AUTO_AUTH = str2bool(os.environ.get('LMS_AUTO_AUTH', False))
LMS_HTTPS = str2bool(os.environ.get('LMS_HTTPS', True))
ENROLLMENT_API_URL = os.environ.get('ENROLLMENT_API_URL', LMS_URL_ROOT + '/api/enrollment/v1')
BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD')

if ENABLE_OAUTH2_TESTS and not all([LMS_URL_ROOT, LMS_USERNAME, LMS_PASSWORD]):
    raise RuntimeError('LMS settings are required to run OAuth2 tests.')

ENABLE_COUPON_ADMIN_TESTS = str2bool(os.environ.get('ENABLE_COUPON_ADMIN_TESTS', False))
