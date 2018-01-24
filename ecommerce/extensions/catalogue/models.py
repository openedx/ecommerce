from django.db import models
from django.db.models.signals import post_init, post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from oscar.apps.catalogue.abstract_models import AbstractProduct

from ecommerce.core.constants import (
    COUPON_PRODUCT_CLASS_NAME,
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    SEAT_PRODUCT_CLASS_NAME,
    DIGITAL_BOOK_PRODUCT_CLASS_NAME
)
from ecommerce.core.utils import log_message_and_raise_validation_error


class Product(AbstractProduct):
    course = models.ForeignKey(
        'courses.Course', null=True, blank=True, related_name='products', on_delete=models.CASCADE
    )
    expires = models.DateTimeField(null=True, blank=True,
                                   help_text=_('Last date/time on which this product can be purchased.'))
    original_expires = None

    @property
    def is_seat_product(self):
        return self.get_product_class().name == SEAT_PRODUCT_CLASS_NAME

    @property
    def is_enrollment_code_product(self):
        return self.get_product_class().name == ENROLLMENT_CODE_PRODUCT_CLASS_NAME

    @property
    def is_course_entitlement_product(self):
        return self.get_product_class().name == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME

    @property
    def is_digital_book_product(self):
        return self.get_product_class().name == DIGITAL_BOOK_PRODUCT_CLASS_NAME

    @property
    def is_coupon_product(self):
        return self.get_product_class().name == COUPON_PRODUCT_CLASS_NAME

    def save(self, *args, **kwargs):
        try:
            if not isinstance(self.attr.note, basestring) and self.attr.note is not None:
                log_message_and_raise_validation_error(
                    'Failed to create Product. Product note value must be of type string'
                )
        except AttributeError:
            pass
        super(Product, self).save(*args, **kwargs)  # pylint: disable=bad-super-call


@receiver(post_init, sender=Product)
def update_original_expires(sender, **kwargs):  # pylint: disable=unused-argument
    """Updates original_expires value of an instance.

    The original_expires value is used to save a database call when updating a
    seat's enrollment code expires field.
    """
    instance = kwargs['instance']
    instance.original_expires = instance.expires


@receiver(post_save, sender=Product)
def update_enrollment_code(sender, **kwargs):  # pylint: disable=unused-argument
    """Updates a seat's enrollment code when the seat is updated.

    Whenever a seat's expires field is updated, the enrollment code's expires
    field for that seat needs to be updated in these cases:
        * the enrollment code's expires field was not already set
        * the enrollment code's expires field was set and is not less than the
          seat's one (if it is less that means the enrollment code was
          deactivated manually, in which case it cannot be activated again
          automatically here)
    """
    instance = kwargs['instance']
    if instance.is_seat_product and (instance.expires != instance.original_expires):
        enrollment_code = instance.course.get_enrollment_code()
        if enrollment_code and (enrollment_code.expires is None or enrollment_code.expires >= instance.expires):
            enrollment_code.expires = instance.expires
            enrollment_code.save()
        instance.original_expires = instance.expires


class Catalog(models.Model):
    name = models.CharField(max_length=255)
    partner = models.ForeignKey('partner.Partner', related_name='catalogs', on_delete=models.CASCADE)
    stock_records = models.ManyToManyField('partner.StockRecord', blank=True, related_name='catalogs')

    def __unicode__(self):
        return u'{id}: {partner_code}-{catalog_name}'.format(
            id=self.id,
            partner_code=self.partner.short_code,
            catalog_name=self.name
        )

from oscar.apps.catalogue.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
