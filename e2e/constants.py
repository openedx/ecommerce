ADDRESS_US = {
    'country': 'US',
    'state': 'MA',
    'line1': '141 Portland Ave.',
    'line2': '9th Floor',
    'city': 'Cambridge',
    'postal_code': '02141',
}

ADDRESS_FR = {
    'country': 'FR',
    'state': None,
    'line1': 'Champ de Mars',
    'line2': '5 Avenue Anatole',
    'city': 'Paris',
    'postal_code': '75007',
}

LOGOUT_REDIRECT_URL = "http://edx.devstack.lms:18000/"

#Conditions:
# Course should be exist on ecommerce and discovery as verified course
# Course should be currently available (course-start-date < now > course-end-date)

TEST_COURSE_KEY = 'course-v1:edX+E2E-101+course'
