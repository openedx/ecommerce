from __future__ import unicode_literals

import logging

from django.conf import settings
from django.db.models import Q
from oscar.core.loading import get_model

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.extensions.catalogue.utils import generate_sku

logger = logging.getLogger(__name__)
Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


def create_parent_course_entitlement(name, UUID):
    """ Create the parent course entitlement product if it does not already exist. """
    parent, created = Product.objects.get_or_create(
        structure=Product.PARENT,
        product_class=ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME),
        title='Parent Course Entitlement for {}'.format(name),
    )

    if created:
        logger.debug('Created new parent course_entitlement [%d] for [%s].', parent.id, UUID)
    else:
        logger.debug('Parent course_entitlement [%d] already exists for [%s].', parent.id, UUID)

    ProductCategory.objects.get_or_create(category=Category.objects.get(name='Course Entitlements'), product=parent)
    parent.title = 'Parent Course Entitlement for {}'.format(name)
    parent.is_discountable = True
    parent.attr.UUID = UUID
    parent.save()

    return parent, created


def create_or_update_course_entitlement(certificate_type, price, partner, UUID, name):
    """ Create or Update Course Entitlement Products """

    certificate_type = certificate_type.lower()
    UUID = unicode(UUID)

    certificate_type_query = Q(
        title='Course {}'.format(name),
        attributes__name='certificate_type',
        attribute_values__value_text=certificate_type,
    )

    try:
        parent_entitlement, __ = create_parent_course_entitlement(name, UUID)
        all_products = parent_entitlement.children.all().prefetch_related('stockrecords')
        course_entitlement = all_products.get(certificate_type_query)
    except Product.DoesNotExist:
        course_entitlement = Product()

    course_entitlement.structure = Product.CHILD
    course_entitlement.is_discountable = True
    course_entitlement.title = 'Course {}'.format(name)
    course_entitlement.attr.certificate_type = certificate_type
    course_entitlement.attr.UUID = UUID
    course_entitlement.parent = parent_entitlement
    course_entitlement.save()

    StockRecord.objects.update_or_create(
        product=course_entitlement, partner=partner,
        defaults={
            'product': course_entitlement,
            'partner': partner,
            'partner_sku': generate_sku(course_entitlement, partner),
            'price_excl_tax': price,
            'price_currency': settings.OSCAR_DEFAULT_CURRENCY,
        }
    )

    logger.info(
        'Course entitlement product stock record with certificate type [%s] for [%s] does not exist. '
        'Instantiated a new instance.',
        certificate_type,
        UUID
    )

    return course_entitlement
