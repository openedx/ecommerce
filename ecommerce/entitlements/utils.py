from __future__ import unicode_literals

import logging

from django.conf import settings

from django.db.models import Q
from oscar.core.loading import get_model


from ecommerce.core.constants import COURSE_ENTITLEMENT_CLASS_NAME
from ecommerce.extensions.catalogue.utils import generate_sku

logger = logging.getLogger(__name__)
Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


def create_parent_course_entitlement(name, course_id):
    """ Create the parent course entitlement product if it does not already exist. """
    parent, created = Product.objects.get_or_create(
        structure=Product.PARENT,
        product_class=ProductClass.objects.get(name=COURSE_ENTITLEMENT_CLASS_NAME),
    )
    ProductCategory.objects.get_or_create(category=Category.objects.get(name='Course Entitlements'), product=parent)
    parent.title = 'Course Entitlement in {}'.format(name)
    parent.is_discountable = True
    parent.attr.course_key = course_id
    parent.save()

    if created:
        logger.debug('Created new parent course_entitlement [%d] for [%s].', parent.id, course_id)
    else:
        logger.debug('Parent course_entitlement [%d] already exists for [%s].', parent.id, course_id)

    return parent


def create_or_update_course_entitlement(certificate_type, price, partner, course_id, name):
    """
    Course Entitlement Products
    """
    certificate_type = certificate_type.lower()
    course_id = unicode(course_id)

    certificate_type_query = Q(
        title='Course Entitlement in {}'.format(name),
        attributes__name='certificate_type',
        attribute_values__value_text=certificate_type
    )

    try:
        parent_entitlement = Product.objects.get(product_class__name=COURSE_ENTITLEMENT_CLASS_NAME, structure=Product.PARENT)
        all_products = parent_entitlement.children.all().prefetch_related('stockrecords')
        course_entitlement = all_products.get(certificate_type_query)
    except:
        course_entitlement = Product()
        parent_entitlement = create_parent_course_entitlement(name, course_id)

    course_entitlement.structure = Product.CHILD
    course_entitlement.is_discountable = True
    course_entitlement.title = 'Course Entitlement in {}'.format(name)
    course_entitlement.attr.certificate_type = certificate_type
    course_entitlement.attr.course_key = course_id
    course_entitlement.parent = parent_entitlement
    course_entitlement.save()

    try:
        stock_record = StockRecord.objects.get(product=course_entitlement, partner=partner)
        logger.info(
            'Retrieved course_entitlement product stock record with certificate type [%s] for [%s] from database.',
            certificate_type,
            course_id
        )
    except StockRecord.DoesNotExist:
        partner_sku = generate_sku(course_entitlement, partner)
        stock_record = StockRecord(product=course_entitlement, partner=partner, partner_sku=partner_sku)
        logger.info(
            'Course course entitlement product stock record with certificate type [%s] for [%s] does not exist. '
            'Instantiated a new instance.',
            certificate_type,
            course_id
        )

    stock_record.price_excl_tax = price
    stock_record.price_currency = settings.OSCAR_DEFAULT_CURRENCY
    stock_record.save()
