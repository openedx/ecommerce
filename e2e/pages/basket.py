import re

from e2e.config import BULK_PURCHASE_SKU
from e2e.pages.ecommerce import EcommerceAppPage


class BasketPage(EcommerceAppPage):
    path = 'basket'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Basket')


class BasketAddProductPage(EcommerceAppPage):
    path = 'basket/single-item/?sku={}'.format(BULK_PURCHASE_SKU)

    def _quantity_selector(self):
        return "input[name='form-0-quantity']"

    def is_browser_on_page(self):
        return self.browser.title.startswith('Basket')

    def get_product_subtotal(self):
        price = self.q(css="div.price").first.text[0]
        return float(re.sub(r'[^0-9.]', '', price))

    def get_product_quantity(self):
        quantity = int(self.q(css="#id_form-0-quantity").first.attrs('value')[0])
        return quantity

    def update_product_quantity(self, quantity=1):
        self.q(css=self._quantity_selector()).fill(quantity)
        self.q(css="div.checkout-quantity button.btn").click()
