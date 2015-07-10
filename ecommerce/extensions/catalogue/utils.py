from hashlib import md5


def generate_sku(product):
    """
    Generates a SKU for the given partner and and product combination.

    Example: 76E4E71
    """
    # Note: This currently supports seats. In the future, this should
    # be updated to accommodate other product classes.
    _hash = u' '.join((product.attr.certificate_type.lower(),
                       product.attr.course_key.lower(),
                       unicode(product.attr.id_verification_required)))
    _hash = md5(_hash)
    _hash = _hash.hexdigest()[-7:]
    return _hash.upper()
