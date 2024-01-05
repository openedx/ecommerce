import logging
import time

import jwt
from django.contrib.staticfiles.storage import staticfiles_storage
from oscar.core.loading import get_model
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder

Product = get_model('catalogue', 'Product')
APP_STORE_BASE_URL = "https://api.appstoreconnect.apple.com"
logger = logging.getLogger(__name__)

def products_in_basket_already_purchased(user, basket, site):
    """
    Check if products in a basket are already purchased by a user.
    """
    products = Product.objects.filter(line__order__basket=basket)
    for product in products:
        if not product.is_enrollment_code_product and \
                UserAlreadyPlacedOrder.user_already_placed_order(user=user, product=product, site=site):
            return True
    return False

def create_ios_skus(course, ios_sku, configuration):
    headers = get_auth_headers(configuration)
    try:
        in_app_purchase_id = create_inapp_purchase(course, ios_sku, configuration['apple_id'], headers)
        localize_inapp_purchase(in_app_purchase_id, headers)
        apply_price_of_inapp_purchase(course['price'], in_app_purchase_id, headers)
        upload_screenshot_of_inapp_purchase(in_app_purchase_id, headers)
        submit_in_app_purchase_for_review(in_app_purchase_id, headers)
    except AppStoreRequestException as store_exception:
        sku_error_msg = "{}  for course {} with sku {}".format(str(store_exception), course['key'], ios_sku)
        logger.error(sku_error_msg)
        return sku_error_msg

def request_connect_store(url, headers, data={}, method="post"):

    http = Session()
    retries = Retry(
        total=3,
        backoff_factor=0.1,
        status_forcelist=[502, 503, 504, 408, 429],
        allowed_methods={'POST', "GET", "PUT", "PATCH"},
    )
    http.mount('https://', HTTPAdapter(max_retries=retries))
    if method == "post":
        return http.post(url, json=data, headers=headers)
    elif method == "get":
        return http.get(url, headers=headers)
    elif method == "patch":
        return http.patch(url, json=data, headers=headers)
    elif method == "put":
        return http.put(url, data=data, headers=headers)


def get_auth_headers(configuration):

    headers = {
        "kid": configuration['key_id'],
        "typ": "JWT",
        "alg": "ES256"
    }

    payload = {
        "iss": configuration['issuer_id'],
        "exp": round(time.time()) + 60 * 20,  # Token expiration time (20 minutes)
        "aud": "appstoreconnect-v1",
        "bid": configuration['ios_bundle_id']
    }

    private_key = configuration['private_key']
    logger.error(private_key)
    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    return headers

def create_inapp_purchase(course, ios_sku, apple_id, headers):

    url = APP_STORE_BASE_URL + "/v2/inAppPurchases"
    data = {
                "data": {
                    "type": "inAppPurchases",
                    "attributes": {
                        "name": course['key'],
                        "productId": ios_sku,
                        "inAppPurchaseType": "NON_CONSUMABLE",
                        "reviewNote": 'This in-app purchase will unlock all the content of the course {course_name}\n\n'
                                      'For testing the end-to-end payment flow, please follow the following steps:\n1. '
                                      'Go to the Discover tab\n2. Search for "{course_name}"\n3. Enroll in the course'
                                      ' "{course_name}"\n4. Hit \"Upgrade to access more features\", it will open a '
                                      'detail unlock features page\n5. Hit "Upgrade now for ${course_price}" from the'
                                      ' detail page'.format(course_name=course['name'], course_price=course['price']),
                        "availableInAllTerritories": True
                    },
                    "relationships": {
                        "app": {
                            "data": {
                                "type": "apps",
                                "id": apple_id
                            }
                        }
                    }
                }
            }
    response = request_connect_store(url=url, data=data, headers=headers)
    logger.error(response.content)
    logger.error(response.status_code)
    if response.status_code == 201:
        return response.json()["data"]["id"]

    raise AppStoreRequestException("Couldn't create inapp purchase id")

def localize_inapp_purchase(in_app_purchase_id, headers):
    url = APP_STORE_BASE_URL + "/v1/inAppPurchaseLocalizations"
    data = {
            "data": {
                "type": "inAppPurchaseLocalizations",
                "attributes": {
                    "locale": "en-US",
                    "name": "Upgrade Course",
                    "description": "Unlock course activities & certificate"
                },
                "relationships": {
                    "inAppPurchaseV2": {
                        "data": {
                            "type": "inAppPurchases",
                            "id": in_app_purchase_id
                        }
                    }
                }
            }
        }
    response = request_connect_store(url=url, data=data, headers=headers)
    if not response.status_code == 201:
        raise AppStoreRequestException("Couldn't localize purchase")


def apply_price_of_inapp_purchase(price, in_app_purchase_id, headers):
    url = APP_STORE_BASE_URL + ("/v2/inAppPurchases/v2/inAppPurchases/{}/pricePoints?filter[territory]=USA"
                                "&include=territory&limit=8000").format(in_app_purchase_id)

    response = request_connect_store(url=url, headers=headers, method='get')
    if response.status_code != 200:
        raise AppStoreRequestException("Couldn't fetch price points")


    nearest_low_price = nearest_low_price_id = 0
    for price_point in response.json()['data']:
        customer_price = float(price_point['attributes']['customerPrice'])
        if nearest_low_price < customer_price <= price:
            nearest_low_price = customer_price
            nearest_low_price_id = price_point['id']

    if not nearest_low_price:
        raise AppStoreRequestException("Couldn't find nearest low price point")


    url = APP_STORE_BASE_URL + "/v1/inAppPurchasePriceSchedules"
    data = {
            "data": {
                "type": "inAppPurchasePriceSchedules",
                "attributes": {},
                "relationships": {
                    "inAppPurchase": {
                        "data": {
                            "type": "inAppPurchases",
                            "id": in_app_purchase_id
                        }
                    },
                    "manualPrices": {
                        "data": [
                            {
                                "type": "inAppPurchasePrices",
                                "id": "${price}"
                            }
                        ]
                    },
                    "baseTerritory": {
                        "data": {
                            "type": "territories",
                            "id": "USA"
                        }
                    }
                }
            },
            "included": [
                {
                    "id": "${price}",
                    "relationships": {
                        "inAppPurchasePricePoint": {
                            "data": {
                                "type": "inAppPurchasePricePoints",
                                "id": nearest_low_price_id
                            }
                        }
                    },
                    "type": "inAppPurchasePrices",
                    "attributes": {
                        "startDate": None
                    }
                }
            ]
        }
    response = request_connect_store(url=url, data=data, headers=headers)
    if response.status_code != 201:
        raise AppStoreRequestException("Couldn't apply price")


def upload_screenshot_of_inapp_purchase(in_app_purchase_id, headers):
    url = APP_STORE_BASE_URL + "/v1/inAppPurchaseAppStoreReviewScreenshots"
    data = {
            "data": {
                "type": "inAppPurchaseAppStoreReviewScreenshots",
                "attributes": {
                    "fileName": "iOS_IAP.png",
                    "fileSize": 124790
                },
                "relationships": {
                    "inAppPurchaseV2": {
                        "data": {
                            "id": in_app_purchase_id,
                            "type": "inAppPurchases"
                        }
                    }
                }
            }
        }

    response = request_connect_store(url, headers, data=data)
    if not response.status_code == 201:
        raise AppStoreRequestException("Couldn't get screenshot url")

    response = response.json()
    screenshot_id = response['data']['id']
    url = response['data']['attributes']['uploadOperations'][0]['url']
    with staticfiles_storage.open('images/mobile_ios_product_screenshot.png', 'rb') as image:
        img_headers = headers.copy()
        img_headers['Content-Type'] = 'image/png'
        response = request_connect_store(url, headers=img_headers, data=image.read(), method='put')

        if not response.status_code == 200:
            raise AppStoreRequestException("Couldn't upload screenshot")

    url = APP_STORE_BASE_URL + "/v1/inAppPurchaseAppStoreReviewScreenshots/{}".format(screenshot_id)
    data = {
            "data": {
                "type": "inAppPurchaseAppStoreReviewScreenshots",
                "id": screenshot_id,
                "attributes": {
                    "uploaded": True,
                    "sourceFileChecksum": ""
                }
            }
        }

    response = request_connect_store(url, headers, data=data, method='patch')

    if not response.status_code == 200:
        raise AppStoreRequestException("Couldn't finalize screenshot")

    # If we submit right after screenshot upload we'll get error because of delay in screenshot uploading
    response = request_connect_store(url, headers, method='get')
    if not response.status_code == 200:
        logger.info("Couldn't confirm screenshot upload but going ahead with submission")

def submit_in_app_purchase_for_review(in_app_purchase_id, headers):
    url = APP_STORE_BASE_URL + "/v1/inAppPurchaseSubmissions"
    data = {
            "data": {
                "type": "inAppPurchaseSubmissions",
                "relationships": {
                    "inAppPurchaseV2": {
                        "data": {
                            "type": "inAppPurchases",
                            "id": in_app_purchase_id
                        }
                    }
                }
            }
        }
    response = request_connect_store(url=url, data=data, headers=headers)
    if not response.status_code == 201:
        raise AppStoreRequestException("Couldn't submit purchase")

class AppStoreRequestException(Exception):
    pass
