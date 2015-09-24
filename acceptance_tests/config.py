import os


def str2bool(s):
    s = unicode(s)
    return s.lower() in (u'yes', u'true', u't', u'1')


# GENERAL CONFIGURATION
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ENABLE_OAUTH2_TESTS = str2bool(os.environ.get('ENABLE_OAUTH2_TESTS', True))
HONOR_COURSE_ID = os.environ.get('HONOR_COURSE_ID', 'edX/DemoX/Demo_Course')
VERIFIED_COURSE_ID = os.environ.get('VERIFIED_COURSE_ID', 'edX/victor101/Victor_s_test_course')

if ACCESS_TOKEN is None:
    raise RuntimeError('A valid OAuth2 access token is required to run acceptance tests.')
# END GENERAL CONFIGURATION


# OTTO CONFIGURATION
try:
    ECOMMERCE_URL_ROOT = os.environ.get('ECOMMERCE_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('You must provide a valid URL root for the E-Commerce Service to run acceptance tests.')

ECOMMERCE_API_URL = os.environ.get('ECOMMERCE_API_URL', ECOMMERCE_URL_ROOT + '/api/v2')
ECOMMERCE_API_TOKEN = os.environ.get('ECOMMERCE_API_TOKEN', ACCESS_TOKEN)
PAYPAL_EMAIL = os.environ.get('PAYPAL_EMAIL')
PAYPAL_PASSWORD = os.environ.get('PAYPAL_PASSWORD')
# It can be a pain to set up CyberSource for local testing. This flag allows CyberSource
# tests to be disabled.
ENABLE_CYBERSOURCE_TESTS = str2bool(os.environ.get('ENABLE_CYBERSOURCE_TESTS', True))
# END OTTO CONFIGURATION


# LMS CONFIGURATION
try:
    LMS_URL_ROOT = os.environ.get('LMS_URL_ROOT').strip('/')
except AttributeError:
    raise RuntimeError('You must provide a valid URL root for the LMS to run acceptance tests.')

LMS_USERNAME = os.environ.get('LMS_USERNAME')
LMS_EMAIL = os.environ.get('LMS_EMAIL')
LMS_PASSWORD = os.environ.get('LMS_PASSWORD')
LMS_AUTO_AUTH = str2bool(os.environ.get('LMS_AUTO_AUTH', False))
LMS_HTTPS = str2bool(os.environ.get('LMS_HTTPS', True))
ENROLLMENT_API_URL = os.environ.get('ENROLLMENT_API_URL', LMS_URL_ROOT + '/api/enrollment/v1')
ENROLLMENT_API_TOKEN = os.environ.get('ENROLLMENT_API_TOKEN', ACCESS_TOKEN)
BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD')

if ENABLE_OAUTH2_TESTS and not (LMS_URL_ROOT and LMS_USERNAME and LMS_PASSWORD):
    raise RuntimeError('Configuring LMS settings is required to run OAuth2 tests.')
# END LMS CONFIGURATION
