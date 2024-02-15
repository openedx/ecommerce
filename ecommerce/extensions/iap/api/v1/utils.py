import logging
import time

import jwt
import requests
from django.contrib.staticfiles.storage import staticfiles_storage
from oscar.core.loading import get_model
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from ecommerce.extensions.iap.api.v1.constants import IOS_PRODUCT_REVIEW_NOTE
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


def create_ios_product(course, ios_product, configuration):
    """
    Create in app ios product on connect store.
    return error message in case of failure.
    """
    headers = get_auth_headers(configuration)
    try:
        in_app_purchase_id = get_or_create_inapp_purchase(ios_product, course, configuration, headers)
        localize_inapp_purchase(in_app_purchase_id, headers)
        apply_price_of_inapp_purchase(course['price'], in_app_purchase_id, headers)
        upload_screenshot_of_inapp_purchase(in_app_purchase_id, headers)
        set_territories_of_in_app_purchase(in_app_purchase_id, headers)
        return submit_in_app_purchase_for_review(in_app_purchase_id, headers)
    except AppStoreRequestException as store_exception:
        error_msg = "[%s]  for course [%s] with sku [%s]" % (str(store_exception), course['key'],
                                                             ios_product.partner_sku)
        logger.error(error_msg)
        return error_msg


def get_or_create_inapp_purchase(ios_stock_record, course, configuration, headers):
    """
    Returns inapp_purchase_id from product attr
    If not present there create a product on ios store and return its inapp_purchase_id
    """

    in_app_purchase_id = getattr(ios_stock_record.product.attr, 'app_store_id', '')
    if not in_app_purchase_id:
        in_app_purchase_id = create_inapp_purchase(course, ios_stock_record.partner_sku,
                                                   configuration['apple_id'], headers)
        ios_stock_record.product.attr.app_store_id = in_app_purchase_id
        ios_stock_record.product.save()

    return in_app_purchase_id


def request_connect_store(url, headers, data=None, method="post"):
    """ Request the given endpoint with multiple tries and backoff time """
    # Adding backoff and retries because of following two reasons
    # 1. In case there is a connection error or server is busy.
    # 2. Product data needs sometime before it gets updated on server for the final submit call,
    # If we submit product right after image uploading it will return 409 error
    # We will try 3 times with backoff time of 1.5, 3, 12 seconds
    retries = Retry(
        total=3,
        backoff_factor=3,
        status_forcelist=[502, 503, 504, 408, 429, 409],
        method_whitelist={'POST', "GET", "PUT", "PATCH"},
    )
    http = Session()
    http.mount('https://', HTTPAdapter(max_retries=retries))
    try:
        if method == "post":
            response = http.post(url, json=data, headers=headers)
        elif method == "patch":
            response = http.patch(url, json=data, headers=headers)
        elif method == "put":
            response = http.put(url, data=data, headers=headers)
        elif method == "get":
            response = http.get(url, headers=headers)
    except requests.RequestException as request_exc:
        raise AppStoreRequestException(request_exc) from request_exc

    return response


def get_auth_headers(configuration):
    """ Get Bearer token with headers to call appstore """

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
    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    return headers


def create_inapp_purchase(course, ios_sku, apple_id, headers):
    """ Create in app product and return its id. """

    url = APP_STORE_BASE_URL + "/v2/inAppPurchases"
    data = {
        "data": {
            "type": "inAppPurchases",
            "attributes": {
                "name": course['key'],
                "productId": ios_sku,
                "inAppPurchaseType": "NON_CONSUMABLE",
                "reviewNote": IOS_PRODUCT_REVIEW_NOTE.format(course_name=course['name'],
                                                             course_price=course['price']),
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
    if response.status_code == 201:
        return response.json()["data"]["id"]

    raise AppStoreRequestException("Couldn't create inapp purchase id")


def localize_inapp_purchase(in_app_purchase_id, headers):
    """ Localize given in app product with US locale. """

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
    if response.status_code != 201:
        raise AppStoreRequestException("Couldn't localize purchase")


def apply_price_of_inapp_purchase(price, in_app_purchase_id, headers):
    """ Apply price tier to the given in app product. """

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
    """ Upload screenshot for the given product. """
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
    if response.status_code != 201:
        raise AppStoreRequestException("Couldn't get screenshot url")

    response = response.json()
    screenshot_id = response['data']['id']
    url = response['data']['attributes']['uploadOperations'][0]['url']
    with staticfiles_storage.open('images/mobile_ios_product_screenshot.png', 'rb') as image:
        img_headers = headers.copy()
        img_headers['Content-Type'] = 'image/png'
        response = request_connect_store(url, headers=img_headers, data=image.read(), method='put')

        if response.status_code != 200:
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

    if response.status_code != 200:
        raise AppStoreRequestException("Couldn't finalize screenshot")


def set_territories_of_in_app_purchase(in_app_purchase_id, headers):
    url = APP_STORE_BASE_URL + '/v1/territories?limit=200'
    response = request_connect_store(url, headers, method='get')
    if response.status_code != 200:
        raise AppStoreRequestException("Couldn't fetch territories")

    territories = [{'type': territory['type'], 'id': territory['id']}
                   for territory in response.json()['data']]

    url = APP_STORE_BASE_URL + '/v1/inAppPurchaseAvailabilities'
    data = {
        "data": {
            "type": "inAppPurchaseAvailabilities",
            "attributes": {
                "availableInNewTerritories": True
            },
            "relationships": {
                "availableTerritories": {
                    "data": territories
                },
                "inAppPurchase": {
                    "data": {
                        "id": in_app_purchase_id,
                        "type": "inAppPurchases"
                    }
                }
            }
        }
    }

    response = request_connect_store(url, headers, data=data)

    if response.status_code != 201:
        raise AppStoreRequestException("Couldn't modify territories of inapp purchase")


def submit_in_app_purchase_for_review(in_app_purchase_id, headers):
    """ Submit in app purchase for the final review by appstore. """
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
    if response.status_code != 201:
        raise AppStoreRequestException("Couldn't submit purchase")


class AppStoreRequestException(Exception):
    pass
