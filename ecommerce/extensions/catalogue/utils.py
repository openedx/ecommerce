from hashlib import md5


def generate_sku(product, partner):
    """
    Generates a SKU for the given partner and and product combination.

    Example: 76E4E71
    """
    # Note: This currently supports enrollment codes and seats.
    # A new product type can be added via a new else if block.
    if product.product_class and \
    product.product_class.slug == u'enrollment_code':
        _hash = u' '.join((
            unicode(getattr(product.attr, 'catalog', '')),
            unicode(getattr(product.attr, 'client', '')),
            str(partner.id)
        ))
    else: 
        # Seats
        _hash = u' '.join((
            getattr(product.attr, 'certificate_type', ''),
            product.attr.course_key,
            unicode(product.attr.id_verification_required),
            getattr(product.attr, 'credit_provider', ''),
            str(partner.id)
        ))

    _hash = md5(_hash.lower())
    _hash = _hash.hexdigest()[-7:]

    return _hash.upper()
