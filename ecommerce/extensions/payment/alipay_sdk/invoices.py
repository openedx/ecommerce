import util as util
from .resource import List, Find, Delete, Create, Update, Post, Resource
from .api import default as default_api


class Invoice(List, Find, Create, Delete, Update, Post):
    """Invoice class wrapping the REST v1/invoices/invoice endpoint

    Usage::

        >>> invoice_history = Invoice.all({"count": 5})

        >>> invoice = Invoice.new({})
        >>> invoice.create()     # return True or False
    """
    path = "v1/invoicing/invoices"

    def send(self, refresh_token=None):
        return self.post('send', {}, self, refresh_token=refresh_token)

    def remind(self, attributes):
        return self.post('remind', attributes, self)

    def cancel(self, attributes):
        return self.post('cancel', attributes, self)

    def record_payment(self, attributes):
        return self.post('record-payment', attributes, self)

    def record_refund(self, attributes):
        return self.post('record-refund', attributes, self)

    def delete_external_payment(self, transactionId):
        # /invoicing/invoices/<INVOICE-ID>/payment-records/<TRANSACTION-ID>
        endpoint = util.join_url(self.path, str(self['id']), 'payment-records', str(transactionId))
        return Resource(self.api.delete(endpoint), api=self.api)

    def delete_external_refund(self, transactionId):
        # /invoicing/invoices/<INVOICE-ID>/refund-records/<TRANSACTION-ID>
        endpoint = util.join_url(self.path, str(self['id']), 'refund-records', str(transactionId))
        return Resource(self.api.delete(endpoint), api=self.api)

    def get_qr_code(self, height=500, width=500, api=None):

        # height and width have default value of 500 as in the APIs
        api = api or default_api()

        # Construct url similar to
        # /invoicing/invoices/<INVOICE-ID>/qr-code?height=<HEIGHT>&width=<WIDTH>
        endpoint = util.join_url(self.path, str(self['id']), 'qr-code')
        image_attributes = [('height', height), ('width', width)]
        url = util.join_url_params(endpoint, image_attributes)

        return Resource(self.api.get(url), api=api)

    @classmethod
    def next_invoice_number(cls, api=None):
        api = api or default_api()
        url = util.join_url(cls.path, 'next-invoice-number')
        return Resource(api.post(url), api=api)

    @classmethod
    def search(cls, params=None, api=None):
        api = api or default_api()
        params = params or {}
        path = "v1/invoicing"

        url = util.join_url(path, 'search')

        return Resource(api.post(url, params), api=api)

Invoice.convert_resources['invoices'] = Invoice
Invoice.convert_resources['invoice'] = Invoice
