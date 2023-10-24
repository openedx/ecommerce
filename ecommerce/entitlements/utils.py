

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
        attributes__name='UUID',
        attribute_values__value_text=UUID,
        defaults={
            'title': 'Parent Course Entitlement for {}'.format(name),
            'is_discountable': True,
        },
    )
    parent.attr.UUID = UUID
    parent.attr.save()

    if created:
        logger.debug('Created new parent course_entitlement [%d] for [%s].', parent.id, UUID)
    else:
        logger.debug('Parent course_entitlement [%d] already exists for [%s].', parent.id, UUID)

    ProductCategory.objects.get_or_create(category=Category.objects.get(name='Course Entitlements'), product=parent)

    return parent, created


def get_entitlement(uuid, certificate_type):
    """ Get a Course Entitlement Product """
    uuid_query = Q(
        attributes__name='UUID',
        attribute_values__value_text=str(uuid),
    )
    certificate_type_query = Q(
        attributes__name='certificate_type',
        attribute_values__value_text=certificate_type.lower(),
    )
    return Product.objects.filter(uuid_query).get(certificate_type_query)


def create_or_update_course_entitlement(
    certificate_type, price, partner, UUID, title, id_verification_required=False, credit_provider=False,
    variant_id=None,
):
    """ Create or Update Course Entitlement Products """
    certificate_type = certificate_type.lower()
    UUID = str(UUID)
    has_existing_course_entitlement = False

    try:
        parent_entitlement, __ = create_parent_course_entitlement(title, UUID)
        course_entitlement = get_entitlement(UUID, certificate_type)
        has_existing_course_entitlement = True
    except Product.DoesNotExist:
        course_entitlement = Product()

    course_entitlement.structure = Product.CHILD
    course_entitlement.is_discountable = True
    course_entitlement.title = 'Course {}'.format(title)
    course_entitlement.attr.certificate_type = certificate_type
    course_entitlement.attr.UUID = UUID
    course_entitlement.attr.id_verification_required = id_verification_required
    course_entitlement.attr.credit_provider = credit_provider
    course_entitlement.parent = parent_entitlement
    if variant_id:
        course_entitlement.attr.variant_id = variant_id
    if has_existing_course_entitlement:
        # Calling `save` on the attributes is necessary for any updates to persist. This is not necessary
        # for new attributes, only for existing attributes. This `save` method must be called before saving
        # the associated course entitlement below.
        course_entitlement.attr.save()
    course_entitlement.save()

    __, created = StockRecord.objects.update_or_create(
        product=course_entitlement, partner=partner,
        defaults={
            'product': course_entitlement,
            'partner': partner,
            'partner_sku': generate_sku(course_entitlement, partner),
            'price_excl_tax': price,
            'price_currency': settings.OSCAR_DEFAULT_CURRENCY,
        }
    )

    if created:
        logger.info(
            'Course entitlement product stock record with certificate type [%s] for [%s] does not exist. '
            'Instantiated a new instance.',
            certificate_type,
            UUID
        )

    return course_entitlement
