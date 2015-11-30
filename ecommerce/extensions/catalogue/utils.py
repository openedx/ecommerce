from hashlib import md5


def generate_sku(product, partner):
    """
    Generates a SKU for the given partner and and product combination.

    Example: 76E4E71
    """
    # Note: This currently supports seats. In the future, this should
    # be updated to accommodate other product classes.
    _hash = u' '.join((
        getattr(product.attr, 'certificate_type', ''),
        product.attr.course_key,
        unicode(product.attr.id_verification_required),
        getattr(product.attr, 'credit_provider', ''),
        str(partner.id)
    ))
    md5_hash = md5(_hash.lower())
    digest = md5_hash.hexdigest()[-7:]

    return digest.upper()
