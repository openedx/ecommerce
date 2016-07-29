from oscar.core.loading import get_model

from ecommerce.extensions.fulfillment.status import ORDER


Refund = get_model('refund', 'Refund')
RefundLine = get_model('refund', 'RefundLine')


def find_orders_associated_with_course(user, course_id):
    """
    Returns a list of orders associated with the given user and course.

    Arguments:
        user (User): user who purchased the order(s)
        course_id (str): Identifier of the course associated with the order(s)

    Raises:
        ValueError if course_id is invalid.

    Returns:
        list: orders associated with the course
    """
    # Validate the course_id
    if not course_id or not course_id.strip():
        raise ValueError('"{}" is not a valid course ID.'.format(course_id))

    # If the user has no orders, we cannot possibly return a list of orders eligible for refund.
    if not user.orders.exists():
        return []

    # Find all complete orders associated with the course.
    orders = user.orders.filter(status=ORDER.COMPLETE,
                                lines__product__attribute_values__attribute__code='course_key',
                                lines__product__attribute_values__value_text=course_id)

    return list(orders)


def create_refunds(site, orders, course_id):
    """
    Creates refunds for the given list of orders.

     Arguments:
        orders (list): orders for which refunds should be created
        course_id (str): Identifier of the course associated with the order line(s)

    Returns:
        list: refunds created
    """
    refunds = []

    for order in orders:
        # Find lines associated with the course and not refunded.
        lines = order.lines.filter(refund_lines__id__isnull=True,
                                   product__attribute_values__attribute__code='course_key',
                                   product__attribute_values__value_text=course_id)

        refund = Refund.create_with_lines(site, order, lines)
        if refund is not None:
            refunds.append(refund)

    return refunds
