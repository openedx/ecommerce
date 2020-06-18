

from oscar.core.loading import get_model

from ecommerce.extensions.fulfillment.status import ORDER

Option = get_model('catalogue', 'Option')
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


def create_refunds_for_entitlement(order, entitlement_uuid):
    """
    Creates a refund for a given order and entitlement

    Arguments:
    order (Order): The order for which to create the refund
    entitlement_uuid (UUID): The entitlement in the order for which to refund

    Returns:
        list: refunds created
    """
    refunds = []

    entitlement_option = Option.objects.get(code='course_entitlement')

    line = order.lines.get(refund_lines__id__isnull=True,
                           attributes__option=entitlement_option,
                           attributes__value=entitlement_uuid)

    refund = Refund.create_with_lines(order, [line])
    if refund is not None:
        refunds.append(refund)

    return refunds


def create_refunds(orders, course_id):
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

        refund = Refund.create_with_lines(order, lines)
        if refund is not None:
            refunds.append(refund)

    return refunds
