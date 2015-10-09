import requests
from ecommerce.settings import get_lms_url


def get_course_price(course_id, course_mode, access_token):
    url = get_lms_url('api/commerce/v1/courses/{}'.format(course_id))

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + access_token
    }

    response = requests.get(url, headers=headers)
    for mode in response.json()['modes']:
        if mode['name'] == course_mode:
            return mode['price']

    raise Exception('No {} mode for course {}'.format(course_mode, course_id))
