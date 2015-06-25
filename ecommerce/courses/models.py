import logging

from django.db import models, transaction
from oscar.core.loading import get_model
from simple_history.models import HistoricalRecords
import waffle
from ecommerce.courses.exceptions import PublishFailed

from ecommerce.courses.publishers import LMSPublisher

logger = logging.getLogger(__name__)
ProductClass = get_model('catalogue', 'ProductClass')


class Course(models.Model):
    id = models.CharField(null=False, max_length=255, primary_key=True, verbose_name='ID')
    name = models.CharField(null=False, max_length=255)
    history = HistoricalRecords()

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super(Course, self).save(force_insert, force_update, using, update_fields)

        if waffle.switch_is_active('publish_course_modes_to_lms'):
            if not LMSPublisher().publish(self):
                # Raise an exception to force a rollback
                raise PublishFailed('Failed to publish {}'.format(self.id))
        else:
            logger.debug('Course mode publishing is not enabled. Commerce changes will not be published!')

    @classmethod
    def is_mode_verified(cls, mode):
        """ Returns True if the mode is verified, otherwise False. """
        return mode.lower() in ('verified', 'professional', 'credit')

    @classmethod
    def certificate_type_for_mode(cls, mode):
        mode = mode.lower()

        if mode == 'no-id-professional':
            return 'professional'

        return mode

    @property
    def seat_products(self):
        """ Returns a list of course seat Products related to this course. """
        seat_product_class = ProductClass.objects.get(slug='seat')
        products = set()

        for product in self.products.all():
            if product.get_product_class() == seat_product_class:
                if product.is_parent:
                    products.update(product.children.all())
                else:
                    products.add(product)

        return list(products)

    def __unicode__(self):
        return self.id
