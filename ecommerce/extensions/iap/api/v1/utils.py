

from oscar.core.loading import get_model

from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder

Product = get_model('catalogue', 'Product')


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
