# coding=utf-8
from __future__ import division

import base64
import datetime
import requests
import json
import logging
import os
import platform
import ssl

import util as util
from . import exceptions
from .config import __version__, __endpoint_map__

import json
from datetime import datetime
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA, SHA256
from Crypto.PublicKey import RSA

from .compability import quote_plus, urlopen, decodebytes, encodebytes, b
from .exceptions import AliPayException, AliPayValidationError

log = logging.getLogger(__name__)


class Api(object):
    # User-Agent for HTTP request
    ssl_version = "" if util.older_than_27() else ssl.OPENSSL_VERSION
    ssl_version_info = None if util.older_than_27() else ssl.OPENSSL_VERSION_INFO
    library_details = "requests %s; python %s; %s" % (
        requests.__version__, platform.python_version(), ssl_version)
    user_agent = "PayPalSDK/PayPal-Python-SDK %s (%s)" % (
        __version__, library_details)

    def __init__(self, options=None, **kwargs):
        """Create API object

        Usage::
            >>> api = paypalrestsdk.Api(mode="sandbox", client_id='CLIENT_ID', client_secret='CLIENT_SECRET',
             ssl_options={"cert": "/path/to/server.pem"})
        """
        kwargs = util.merge_dict(options or {}, kwargs)

        self.mode = kwargs.get("mode", "sandbox")

        if self.mode != "live" and self.mode != "sandbox":
            raise exceptions.InvalidConfig("Configuration Mode Invalid", "Received: %s" % (self.mode),
                                           "Required: live or sandbox")

        self.endpoint = kwargs.get("endpoint", self.default_endpoint())
        self.token_endpoint = kwargs.get("token_endpoint", self.endpoint)
        # Mandatory parameter, so not using `dict.get`
        self.app_id = kwargs["app_id"]
        # Mandatory parameter, so not using `dict.get`
        self.private_key = '-----BEGIN PRIVATE KEY-----\n{0}\n-----END PRIVATE KEY-----'.format(kwargs["private_key"])
        self.alipay_public_key = u'-----BEGIN PUBLIC KEY-----\n{0}\n-----END PUBLIC KEY-----'.format(kwargs["alipay_public_key"])
        self.sign_type = kwargs["sign_type"]
        self.charset = kwargs["charset"]
        self.proxies = kwargs.get("proxies", None)
        self.token_hash = None
        self.token_request_at = None
        # setup SSL certificate verification if private certificate provided
        ssl_options = kwargs.get("ssl_options", {})
        if "cert" in ssl_options:
            os.environ["REQUESTS_CA_BUNDLE"] = ssl_options["cert"]

        if kwargs.get("token"):
            self.token_hash = {
                "access_token": kwargs["token"], "token_type": "Bearer"}

        self.options = kwargs

    def _sign(self, unsigned_string):
        key = RSA.importKey(self.private_key)
        signer = PKCS1_v1_5.new(key)
        if self.sign_type == "RSA":
            signature = signer.sign(SHA.new(b(unsigned_string)))
        else:
            signature = signer.sign(SHA256.new(b(unsigned_string)))
        sign = encodebytes(signature).decode("utf8").replace("\n", "")
        return sign

    def _ordered_data(self, data):
        complex_keys = []
        for key, value in data.items():
            if isinstance(value, dict):
                complex_keys.append(key)

        for key in complex_keys:
            data[key] = json.dumps(data[key], separators=(',', ':'))

        return sorted([(k, v) for k, v in data.items()])

    def build_body(
            self, method, biz_content, return_url=None, notify_url=None, append_auth_token=False
    ):
        data = {
            "app_id": self.app_id,
            "method": method,
            "charset": "utf-8",
            "sign_type": self.sign_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": biz_content
        }
        if append_auth_token:
            data["app_auth_token"] = self.app_auth_token

        if return_url is not None:
            data["return_url"] = return_url

        if method in (
                "alipay.trade.app.pay", "alipay.trade.wap.pay", "alipay.trade.page.pay",
                "alipay.trade.pay"
        ):

            if notify_url is not None:
                data["notify_url"] = notify_url

        return data

    def sign_data(self, data):
        data.pop("sign", None)
        # 排序后的字符串
        unsigned_items = self._ordered_data(data)
        unsigned_string = "&".join("{}={}".format(k, v) for k, v in unsigned_items)
        sign = self._sign(unsigned_string)
        ordered_items = self._ordered_data(data)
        quoted_string = "&".join("{}={}".format(k, quote_plus(str(v))) for k, v in ordered_items)
        # 获得最终的订单信息字符串
        signed_string = quoted_string + "&sign=" + quote_plus(sign)
        return signed_string

    def _verify(self, raw_content, signature):
        # 开始计算签名
        key = RSA.importKey(self.alipay_public_key)
        signer = PKCS1_v1_5.new(key)
        if self.sign_type == "RSA":
            digest = SHA.new()
        else:
            digest = SHA256.new()
        digest.update(raw_content.encode("utf8"))
        if signer.verify(digest, decodebytes(signature.encode("utf8"))):
            return True
        return False

    def verify(self, data, signature):
        if "sign_type" in data:
            sign_type = data.pop("sign_type")
            if sign_type != self.sign_type:
                raise AliPayException(None, "Unknown sign type: {}".format(sign_type))
        # 排序后的字符串
        unsigned_items = self._ordered_data(data)
        message = "&".join(u"{}={}".format(k, v) for k, v in unsigned_items)
        return self._verify(message, signature)

    def api(self, api_name, **kwargs):
        """
        alipay.api("alipay.trade.page.pay", **kwargs) ==> alipay.api_alipay_trade_page_pay(**kwargs)
        """
        api_name = api_name.replace(".", "_")
        key = "api_" + api_name
        if hasattr(self, key):
            return getattr(self, key)
        raise AttributeError("Unknown attribute" + api_name)

    def api_alipay_trade_wap_pay(
            self, subject, out_trade_no, total_amount,
            return_url=None, notify_url=None, **kwargs
    ):
        biz_content = {
            "subject": subject,
            "out_trade_no": out_trade_no,
            "total_amount": total_amount,
            "product_code": "QUICK_WAP_PAY"
        }
        biz_content.update(kwargs)
        data = self.build_body(
            "alipay.trade.wap.pay",
            biz_content,
            return_url=return_url,
            notify_url=notify_url
        )
        return self.sign_data(data)

    def api_alipay_trade_app_pay(
            self, subject, out_trade_no, total_amount, notify_url=None, **kwargs
    ):
        biz_content = {
            "subject": subject,
            "out_trade_no": out_trade_no,
            "total_amount": total_amount,
            "product_code": "QUICK_MSECURITY_PAY"
        }
        biz_content.update(kwargs)
        data = self.build_body("alipay.trade.app.pay", biz_content, notify_url=notify_url)
        return self.sign_data(data)

    def api_alipay_trade_page_pay(self, subject, out_trade_no, total_amount,
                                  return_url=None, notify_url=None, **kwargs):
        biz_content = {
            "subject": subject,
            "out_trade_no": out_trade_no,
            "total_amount": total_amount,
            "product_code": "FAST_INSTANT_TRADE_PAY"
        }

        biz_content.update(kwargs)
        data = self.build_body(
            "alipay.trade.page.pay",
            biz_content,
            return_url=return_url,
            notify_url=notify_url
        )
        return self.sign_data(data)

    def api_alipay_trade_query(self, out_trade_no=None, trade_no=None):
        """
        response = {
          "alipay_trade_query_response": {
            "trade_no": "2017032121001004070200176844",
            "code": "10000",
            "invoice_amount": "20.00",
            "open_id": "20880072506750308812798160715407",
            "fund_bill_list": [
              {
                "amount": "20.00",
                "fund_channel": "ALIPAYACCOUNT"
              }
            ],
            "buyer_logon_id": "csq***@sandbox.com",
            "send_pay_date": "2017-03-21 13:29:17",
            "receipt_amount": "20.00",
            "out_trade_no": "out_trade_no15",
            "buyer_pay_amount": "20.00",
            "buyer_user_id": "2088102169481075",
            "msg": "Success",
            "point_amount": "0.00",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "20.00"
          },
          "sign": ""
        }
        """
        assert (out_trade_no is not None) or (trade_no is not None), \
            "Both trade_no and out_trade_no are None"

        biz_content = {}
        if out_trade_no:
            biz_content["out_trade_no"] = out_trade_no
        if trade_no:
            biz_content["trade_no"] = trade_no
        data = self.build_body("alipay.trade.query", biz_content)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(raw_string, "alipay_trade_query_response")

    def api_alipay_trade_pay(
            self, out_trade_no, scene, auth_code, subject, notify_url=None, **kwargs
    ):
        """
        eg:
            self.api_alipay_trade_pay(
                out_trade_no,
                "bar_code/wave_code",
                auth_code,
                subject,
                total_amount=12,
                discountable_amount=10
            )

        failed response = {
            "alipay_trade_pay_response": {
                "code": "40004",
                "msg": "Business Failed",
                "sub_code": "ACQ.INVALID_PARAMETER",
                "sub_msg": "",
                "buyer_pay_amount": "0.00",
                "invoice_amount": "0.00",
                "point_amount": "0.00",
                "receipt_amount": "0.00"
            },
            "sign": ""
        }
        succeeded response =
            {
              "alipay_trade_pay_response": {
                "trade_no": "2017032121001004070200176846",
                "code": "10000",
                "invoice_amount": "20.00",
                "open_id": "20880072506750308812798160715407",
                "fund_bill_list": [
                  {
                    "amount": "20.00",
                    "fund_channel": "ALIPAYACCOUNT"
                  }
                ],
                "buyer_logon_id": "csq***@sandbox.com",
                "receipt_amount": "20.00",
                "out_trade_no": "out_trade_no18",
                "buyer_pay_amount": "20.00",
                "buyer_user_id": "2088102169481075",
                "msg": "Success",
                "point_amount": "0.00",
                "gmt_payment": "2017-03-21 15:07:29",
                "total_amount": "20.00"
              },
              "sign": ""
            }
        """
        assert scene in ("bar_code", "wave_code"), 'scene not in ("bar_code", "wave_code")'

        biz_content = {
            "out_trade_no": out_trade_no,
            "scene": scene,
            "auth_code": auth_code,
            "subject": subject
        }
        biz_content.update(**kwargs)
        data = self.build_body("alipay.trade.pay", biz_content, notify_url=notify_url)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(raw_string, "alipay_trade_pay_response")

    def api_alipay_trade_refund(self, refund_amount, out_trade_no=None, trade_no=None, **kwargs):
        biz_content = {
            "refund_amount": refund_amount
        }
        biz_content.update(**kwargs)
        if out_trade_no:
            biz_content["out_trade_no"] = out_trade_no
        if trade_no:
            biz_content["trade_no"] = trade_no

        data = self.build_body("alipay.trade.refund", biz_content)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(raw_string, "alipay_trade_refund_response")

    def api_alipay_trade_cancel(self, out_trade_no=None, trade_no=None):
        """
        response = {
        "alipay_trade_cancel_response": {
            "msg": "Success",
            "out_trade_no": "out_trade_no15",
            "code": "10000",
            "retry_flag": "N"
          }
        }
        """

        assert (out_trade_no is not None) or (trade_no is not None), \
            "Both trade_no and out_trade_no are None"

        biz_content = {}
        if out_trade_no:
            biz_content["out_trade_no"] = out_trade_no
        if trade_no:
            biz_content["trade_no"] = trade_no

        data = self.build_body("alipay.trade.cancel", biz_content)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(raw_string, "alipay_trade_cancel_response")

    def api_alipay_trade_precreate(self, subject, out_trade_no, total_amount, **kwargs):
        """
        success response  = {
          "alipay_trade_precreate_response": {
            "msg": "Success",
            "out_trade_no": "out_trade_no17",
            "code": "10000",
            "qr_code": "https://qr.alipay.com/bax03431ljhokirwl38f00a7"
          },
          "sign": ""
        }

        failed response = {
          "alipay_trade_precreate_response": {
            "msg": "Business Failed",
            "sub_code": "ACQ.TOTAL_FEE_EXCEED",
            "code": "40004",
            "sub_msg": "订单金额超过限额"
          },
          "sign": ""
        }

        """
        biz_content = {
            "out_trade_no": out_trade_no,
            "total_amount": total_amount,
            "subject": subject
        }
        biz_content.update(**kwargs)
        data = self.build_body("alipay.trade.precreate", biz_content)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(raw_string, "alipay_trade_precreate_response")

    def api_alipay_fund_trans_toaccount_transfer(
            self, out_biz_no, payee_type, payee_account, amount, **kwargs
    ):
        assert payee_type in ("ALIPAY_USERID", "ALIPAY_LOGONID"), "unknown payee type"
        biz_content = {
            "out_biz_no": out_biz_no,
            "payee_type": payee_type,
            "payee_account": payee_account,
            "amount": amount
        }
        biz_content.update(kwargs)
        data = self.build_body("alipay.fund.trans.toaccount.transfer", biz_content)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(
            raw_string, "alipay_fund_trans_toaccount_transfer_response"
        )

    def api_alipay_fund_trans_order_query(self, out_biz_no=None, order_id=None):
        if out_biz_no is None and order_id is None:
            raise Exception("Both out_biz_no and order_id are None!")

        biz_content = {}
        if out_biz_no:
            biz_content["out_biz_no"] = out_biz_no
        if order_id:
            biz_content["order_id"] = order_id

        data = self.build_body("alipay.fund.trans.order.query", biz_content)

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(
            raw_string, "alipay_fund_trans_order_query_response"
        )

    def _verify_and_return_sync_response(self, raw_string, response_type):
        """
        return data if verification succeeded, else raise exception
        """

        response = json.loads(raw_string)
        result = response[response_type]
        sign = response["sign"]

        # locate string to be signed
        raw_string = self._get_string_to_be_signed(
            raw_string, response_type
        )

        if not self._verify(raw_string, sign):
            raise AliPayValidationError
        return result

    def _get_string_to_be_signed(self, raw_string, response_type):
        """
        https://doc.open.alipay.com/docs/doc.htm?docType=1&articleId=106120
        从同步返回的接口里面找到待签名的字符串
        """
        left_index = 0
        right_index = 0

        index = raw_string.find(response_type)
        left_index = raw_string.find("{", index)
        index = left_index + 1

        balance = -1
        while balance < 0 and index < len(raw_string) - 1:
            index_a = raw_string.find("{", index)
            index_b = raw_string.find("}", index)

            # 右括号没找到， 退出
            if index_b == -1:
                break
            right_index = index_b

            # 左括号没找到，移动到右括号的位置
            if index_a == -1:
                index = index_b + 1
                balance += 1
            # 左括号出现在有括号之前，移动到左括号的位置
            elif index_a > index_b:
                balance += 1
                index = index_b + 1
            # 左括号出现在右括号之后， 移动到右括号的位置
            else:
                balance -= 1
                index = index_a + 1

        return raw_string[left_index: right_index + 1]

    def default_endpoint(self):
        return __endpoint_map__.get(self.mode)

    def _check_openssl_version(self):
        """
        Check that merchant server has PCI compliant version of TLS
        Print warning if it does not.
        """
        if self.ssl_version_info and self.ssl_version_info < (1, 0, 1, 0, 0):
            log.warning(
                'WARNING: openssl version ' + self.ssl_version + ' detected. Per PCI Security Council mandate \
                (https://github.com/paypal/TLS-update), you MUST update to the latest security library.')

    def request(self, url, method, body=None, headers=None, refresh_token=None):
        """Make HTTP call, formats response and does error handling. Uses http_call method in API class.

        Usage::

            >>> api.request("https://api.sandbox.paypal.com/v1/payments/payment?count=10", "GET", {})
            >>> api.request("https://api.sandbox.paypal.com/v1/payments/payment", "POST", "{}", {} )

        """

        http_headers = util.merge_dict(
            self.headers(refresh_token=refresh_token, headers=headers or {}), headers or {})

        if http_headers.get('PayPal-Request-Id'):
            log.info('PayPal-Request-Id: %s' %
                     (http_headers['PayPal-Request-Id']))

        self._check_openssl_version()

        try:
            return self.http_call(url, method, data=json.dumps(body), headers=http_headers)

        # Format Error message for bad request
        except exceptions.BadRequest as error:
            return {"error": json.loads(error.content)}

        # Handle Expired token
        except exceptions.UnauthorizedAccess as error:
            if (self.token_hash and self.client_id):
                self.token_hash = None
                return self.request(url, method, body, headers)
            else:
                raise error

    def http_call(self, url, method, **kwargs):
        """Makes a http call. Logs response information.
        """
        log.info('Request[%s]: %s' % (method, url))

        if self.mode.lower() != 'live':
            request_headers = kwargs.get("headers", {})
            request_body = kwargs.get("data", {})
            log.debug("Level: " + self.mode)
            log.debug('Request: \nHeaders: %s\nBody: %s' % (
                str(request_headers), str(request_body)))
        else:
            log.info(
                'Not logging full request/response headers and body in live mode for compliance')

        start_time = datetime.datetime.now()
        response = requests.request(
            method, url, proxies=self.proxies, **kwargs)
        duration = datetime.datetime.now() - start_time
        log.info('Response[%d]: %s, Duration: %s.%ss.' % (
            response.status_code, response.reason, duration.seconds, duration.microseconds))

        debug_id = response.headers.get('PayPal-Debug-Id')
        if debug_id:
            log.debug('debug_id: %s' % debug_id)
        if self.mode.lower() != 'live':
            log.debug('Headers: %s\nBody: %s' % (
                str(response.headers), str(response.content)))

        return self.handle_response(response, response.content.decode('utf-8'))

    def handle_response(self, response, content):
        """Validate HTTP response
        """
        status = response.status_code
        if status in (301, 302, 303, 307):
            raise exceptions.Redirection(response, content)
        elif 200 <= status <= 299:
            return json.loads(content) if content else {}
        elif status == 400:
            raise exceptions.BadRequest(response, content)
        elif status == 401:
            raise exceptions.UnauthorizedAccess(response, content)
        elif status == 403:
            raise exceptions.ForbiddenAccess(response, content)
        elif status == 404:
            raise exceptions.ResourceNotFound(response, content)
        elif status == 405:
            raise exceptions.MethodNotAllowed(response, content)
        elif status == 409:
            raise exceptions.ResourceConflict(response, content)
        elif status == 410:
            raise exceptions.ResourceGone(response, content)
        elif status == 422:
            raise exceptions.ResourceInvalid(response, content)
        elif 401 <= status <= 499:
            raise exceptions.ClientError(response, content)
        elif 500 <= status <= 599:
            raise exceptions.ServerError(response, content)
        else:
            raise exceptions.ConnectionError(
                response, content, "Unknown response code: #{response.code}")

    def headers(self, refresh_token=None, headers=None):
        """Default HTTP headers
        """
        token_hash = self.get_token_hash(refresh_token=refresh_token, headers=headers or {})

        return {
            "Authorization": ("%s %s" % (token_hash['token_type'], token_hash['access_token'])),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent
        }

    def get(self, action, headers=None, refresh_token=None):
        """Make GET request

        Usage::

            >>> api.get("v1/payments/payment?count=1")
            >>> api.get("v1/payments/payment/PAY-1234")
        """
        return self.request(util.join_url(self.endpoint, action), 'GET', headers=headers or {},
                            refresh_token=refresh_token)

    def post(self, action, params=None, headers=None, refresh_token=None):
        """Make POST request

        Usage::

            >>> api.post("v1/payments/payment", { 'indent': 'sale' })
            >>> api.post("v1/payments/payment/PAY-1234/execute", { 'payer_id': '1234' })

        """
        return self.request(util.join_url(self.endpoint, action), 'POST', body=params or {}, headers=headers or {},
                            refresh_token=refresh_token)

    def put(self, action, params=None, headers=None, refresh_token=None):
        """Make PUT request

        Usage::

            >>> api.put("v1/invoicing/invoices/INV2-RUVR-ADWQ", { 'id': 'INV2-RUVR-ADWQ', 'status': 'DRAFT'})
        """
        return self.request(util.join_url(self.endpoint, action), 'PUT', body=params or {}, headers=headers or {},
                            refresh_token=refresh_token)

    def patch(self, action, params=None, headers=None, refresh_token=None):
        """Make PATCH request

        Usage::

            >>> api.patch("v1/payments/billing-plans/P-5VH69258TN786403SVUHBM6A", { 'op': 'replace', 'path': '/merchant-preferences'})
        """
        return self.request(util.join_url(self.endpoint, action), 'PATCH', body=params or {}, headers=headers or {},
                            refresh_token=refresh_token)

    def delete(self, action, headers=None, refresh_token=None):
        """Make DELETE request
        """
        return self.request(util.join_url(self.endpoint, action), 'DELETE', headers=headers or {},
                            refresh_token=refresh_token)


class AliPay(Api):
    pass


class ISVAliPay(Api):
    def __init__(self, appid, app_notify_url, app_private_key_path,
                 alipay_public_key_path, sign_type="RSA2", debug=False,
                 app_auth_token=None, app_auth_code=None):
        if not app_auth_token and not app_auth_code:
            raise Exception("Both app_auth_code and app_auth_token are None !!!")

        self._app_auth_token = app_auth_token
        self._app_auth_code = app_auth_code
        super(ISVAliPay, self).__init__(
            appid, app_notify_url, app_private_key_path,
            alipay_public_key_path, sign_type, debug
        )

    @property
    def app_auth_token(self):
        # 没有则换取token
        if not self._app_auth_token:
            result = self.api_alipay_open_auth_token_app(self._app_auth_code)
            self._app_auth_token = result.get("app_auth_token", None)

        if not self._app_auth_token:
            raise Exception("Get auth token by auth code failed: {}".format(self._app_auth_code))
        return self._app_auth_token

    def build_body(self, method, biz_content, return_url=None, append_auth_token=True):

        return super(ISVAliPay, self).build_body(method, biz_content, return_url, append_auth_token)

    def api_alipay_open_auth_token_app(self, refresh_token=None):
        """
        response = {
          "code": "10000",
          "msg": "Success",
          "app_auth_token": "201708BB28623ce3d10f4f62875e9ef5cbeebX07",
          "app_refresh_token": "201708BB108a270d8bb6409890d16175a04a7X07",
          "auth_app_id": "appid",
          "expires_in": 31536000,
          "re_expires_in": 32140800,
          "user_id": "2088xxxxx
        }
        """

        if refresh_token:
            biz_content = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
        else:
            biz_content = {
                "grant_type": "authorization_code",
                "code": self._app_auth_code
            }
        data = self.build_body(
            "alipay.open.auth.token.app",
            biz_content,
            append_auth_token=False
        )

        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(
            raw_string, "alipay_open_auth_token_app_response"
        )

    def api_alipay_open_auth_token_app_query(self):
        biz_content = {
            "app_auth_token": self.app_auth_token
        }
        data = self.build_body(
            "alipay.open.auth.token.app.query",
            biz_content,
            append_auth_token=False
        )
        url = self._gateway + "?" + self.sign_data(data)
        raw_string = urlopen(url, timeout=15).read().decode("utf-8")
        return self._verify_and_return_sync_response(
            raw_string, "alipay_open_auth_token_app_query_response"
        )


__api__ = None


def default():
    """Returns default api object and if not present creates a new one
    By default points to developer sandbox
    """
    global __api__
    if __api__ is None:
        try:
            client_id = os.environ["PAYPAL_CLIENT_ID"]
            client_secret = os.environ["PAYPAL_CLIENT_SECRET"]
        except KeyError:
            raise exceptions.MissingConfig("Required PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET. \
                Refer https://github.com/paypal/rest-api-sdk-python#configuration")

        __api__ = Api(mode=os.environ.get(
            "PAYPAL_MODE", "sandbox"), client_id=client_id, client_secret=client_secret)
    return __api__


def set_config(options=None, **config):
    """Create new default api object with given configuration
    """
    global __api__
    __api__ = Api(options or {}, **config)
    return __api__


configure = set_config
