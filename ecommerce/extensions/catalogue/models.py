

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models.signals import post_init, post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from oscar.apps.catalogue.abstract_models import (
    AbstractCategory,
    AbstractOption,
    AbstractProduct,
    AbstractProductAttribute,
    AbstractProductAttributeValue,
    AbstractProductCategory,
    AbstractProductClass
)
from simple_history.models import HistoricalRecords

from ecommerce.core.constants import (
    COUPON_PRODUCT_CLASS_NAME,
    COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.core.utils import log_message_and_raise_validation_error


class CreateSafeHistoricalRecords(HistoricalRecords):
    """
    Overrides default HistoricalRecords so that newly created rows can avoid being saved to history.

    This prevents errors during migrations with models that have HistoricalRecords and also
    try to create rows as part of their migrations (before the history table is created).
    """
    def post_save(self, instance, created, using=None, **kwargs):
        """
        The only difference between this method and the original is the first line, which omits a check to
        see if the object is newly created:
        https://github.com/treyhunner/django-simple-history/blob/2.7.2/simple_history/models.py#L456
        """
        if hasattr(instance, "skip_history_when_saving"):
            return
        if not kwargs.get("raw", False):  # pragma: no cover
            self.create_historical_record(instance, created and "+" or "~", using=using)

    def post_delete(self, instance, using=None, **kwargs):
        """
        The only difference between this method and the original is the addition of first line, which
        extends "skip_history_when_saving" checks to deletes:
        https://github.com/treyhunner/django-simple-history/blob/2.7.2/simple_history/models.py#L460
        """
        if hasattr(instance, "skip_history_when_saving"):
            return

        if self.cascade_delete_history:  # pragma: no cover
            manager = getattr(instance, self.manager_name)
            manager.using(using).all().delete()
        else:
            self.create_historical_record(instance, "-", using=using)


class Product(AbstractProduct):
    course = models.ForeignKey(
        'courses.Course', null=True, blank=True, related_name='products', on_delete=models.CASCADE
    )
    expires = models.DateTimeField(null=True, blank=True,
                                   help_text=_('Last date/time on which this product can be purchased.'))
    original_expires = None

    history = HistoricalRecords()

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
    def is_coupon_product(self):
        return self.get_product_class().name == COUPON_PRODUCT_CLASS_NAME

    def save(self, *args, **kwargs):
        try:
            if not isinstance(self.attr.note, str) and self.attr.note is not None:
                log_message_and_raise_validation_error(
                    'Failed to create Product. Product note value must be of type string'
                )
        except AttributeError:
            pass

        try:
            if self.attr.notify_email is not None:
                validate_email(self.attr.notify_email)
        except ValidationError:
            log_message_and_raise_validation_error(
                'Notification email must be a valid email address.'
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


class ProductAttributeValue(AbstractProductAttributeValue):
    history = CreateSafeHistoricalRecords()


class Catalog(models.Model):
    name = models.CharField(max_length=255)
    partner = models.ForeignKey('partner.Partner', related_name='catalogs', on_delete=models.CASCADE)
    stock_records = models.ManyToManyField('partner.StockRecord', blank=True, related_name='catalogs')

    def __str__(self):
        return u'{id}: {partner_code}-{catalog_name}'.format(
            id=self.id,
            partner_code=self.partner.short_code,
            catalog_name=self.name
        )


class Category(AbstractCategory):
    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/edx/course-discovery/pull/332
    history = CreateSafeHistoricalRecords(excluded_fields=['slug'])


class Option(AbstractOption):
    # Do not record the code field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/edx/course-discovery/pull/332
    history = CreateSafeHistoricalRecords(excluded_fields=['code'])


class ProductClass(AbstractProductClass):
    # Do not record the slug field in the history table because AutoSlugField is not compatible with
    # django-simple-history.  Background: https://github.com/edx/course-discovery/pull/332
    history = CreateSafeHistoricalRecords(excluded_fields=['slug'])


class ProductCategory(AbstractProductCategory):
    history = CreateSafeHistoricalRecords()


class ProductAttribute(AbstractProductAttribute):
    history = CreateSafeHistoricalRecords()


from oscar.apps.catalogue.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,wrong-import-order,ungrouped-imports
