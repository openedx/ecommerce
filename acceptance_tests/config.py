import os


def str2bool(s):
    s = unicode(s)
    return s.lower() in (u"yes", u"true", u"t", u"1")


ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN', 'edx')

# Application configuration
APP_SERVER_URL = os.environ.get('APP_SERVER_URL', 'http://localhost:8002').strip('/')
ECOMMERCE_API_SERVER_URL = os.environ.get('ECOMMERCE_API_SERVER_URL', APP_SERVER_URL + '/api/v2').strip('/')
ECOMMERCE_API_SIGNING_KEY = os.environ.get('ECOMMERCE_API_SIGNING_KEY', 'edx')
ECOMMERCE_API_TOKEN = os.environ.get('ECOMMERCE_API_AUTH_TOKEN', ACCESS_TOKEN)

# Amount of time allotted for processing an order. This value is used to match newly-placed orders in testing, and
# account for processing delays such as load times
ORDER_PROCESSING_TIME = int(os.environ.get('ORDER_PROCESSING_TIME', 15))

# Test configuration
ENABLE_AUTO_AUTH = str2bool(os.environ.get('ENABLE_AUTO_AUTH', False))
ENABLE_OAUTH_TESTS = str2bool(os.environ.get('ENABLE_OAUTH_TESTS', True))
COURSE_ID = os.environ.get('COURSE_ID', 'edX/DemoX/Demo_Course')
VERIFIED_COURSE_ID = os.environ.get('VERIFIED_COURSE_ID', 'edX/victor101/Victor_s_test_course')

# LMS configuration
BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD')
LMS_URL = os.environ.get('LMS_URL').strip('/')
LMS_USERNAME = os.environ.get('LMS_USERNAME')
LMS_EMAIL = os.environ.get('LMS_EMAIL')
LMS_PASSWORD = os.environ.get('LMS_PASSWORD')
HTTPS_RECEIPT_PAGE = str2bool(os.environ.get('HTTPS_RECEIPT_PAGE', True))

if ENABLE_OAUTH_TESTS and not (LMS_URL and LMS_USERNAME and LMS_PASSWORD):
    raise Exception('LMS settings must be set in order to test OAuth.')

# Enrollment API configuration
ENROLLMENT_API_URL = os.environ.get('ENROLLMENT_API_URL')
if not ENROLLMENT_API_URL:
    ENROLLMENT_API_URL = '{}/api/enrollment/v1'.format(LMS_URL)

ENROLLMENT_API_TOKEN = os.environ.get('ENROLLMENT_API_TOKEN', ACCESS_TOKEN)
