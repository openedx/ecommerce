from __future__ import unicode_literals
import logging

from django.db import models, transaction
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from simple_history.models import HistoricalRecords

from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.catalogue.utils import generate_sku

logger = logging.getLogger(__name__)
Category = get_model('catalogue', 'Category')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


class Course(models.Model):
    id = models.CharField(null=False, max_length=255, primary_key=True, verbose_name='ID')
    name = models.CharField(null=False, max_length=255)
    verification_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Last date/time on which verification for this product can be submitted.')
    )
    history = HistoricalRecords()
    thumbnail_url = models.URLField(null=True, blank=True)

    def __unicode__(self):
        return unicode(self.id)

    def _create_parent_seat(self):
        """ Create the parent seat product if it does not already exist. """
        slug = 'parent-cs-{}'.format(slugify(unicode(self.id)))
        defaults = {
            'is_discountable': True,
            'structure': Product.PARENT,
            'product_class': ProductClass.objects.get(slug='seat')
        }
        parent, created = self.products.get_or_create(slug=slug, defaults=defaults)
        ProductCategory.objects.get_or_create(category=Category.objects.get(name='Seats'), product=parent)
        parent.title = 'Seat in {}'.format(self.name)
        parent.attr.course_key = self.id
        parent.save()

        if created:
            logger.debug('Created new parent seat [%d] for [%s].', parent.id, self.id)
        else:
            logger.debug('Parent seat [%d] already exists for [%s].', parent.id, self.id)

    @transaction.atomic
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super(Course, self).save(force_insert, force_update, using, update_fields)
        self._create_parent_seat()

    def publish_to_lms(self):
        """ Publish Course and Products to LMS. """
        return LMSPublisher().publish(self)

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
    def type(self):
        """ Returns the type of the course (based on the available seat types). """
        seat_types = [(seat.attr.certificate_type or '').lower() for seat in self.seat_products]
        if 'credit' in seat_types:
            return 'credit'
        elif 'professional' in seat_types or 'no-id-professional' in seat_types:
            return 'professional'
        elif 'verified' in seat_types:
            return 'verified'
        else:
            return 'honor'

    @property
    def parent_seat_product(self):
        """ Returns the course seat parent Product. """
        return self.products.get(product_class__slug='seat', structure=Product.PARENT)

    @property
    def seat_products(self):
        """ Returns a list of course seat Products related to this course. """
        return list(self.parent_seat_product.children.all().prefetch_related('stockrecords'))

    def _get_course_seat_name(self, certificate_type, id_verification_required):
        """ Returns the name for a course seat. """
        name = 'Seat in {course_name} with {certificate_type} certificate'.format(
            course_name=self.name,
            certificate_type=certificate_type)

        if id_verification_required:
            name += ' (and ID verification)'

        return name

    def create_or_update_seat(self, certificate_type, id_verification_required, price, credit_provider=None,
                              expires=None, credit_hours=None):
        """
        Creates course seat products.

        Returns:
            Product:  The seat that has been created or updated.
        """

        certificate_type = certificate_type.lower()
        course_id = unicode(self.id)

        slugs = []
        slug = 'child-cs-{}-{}'.format(certificate_type, slugify(course_id))

        # Note (CCB): Our previous method of slug generation did not account for ID verification. By using a list
        # we can update these seats. This should be removed after the courses have been re-migrated.
        if certificate_type == 'verified':
            slugs.append(slug)

        if id_verification_required:
            slug += '-id-verified'
        slugs.append(slug)
        slugs = set(slugs)

        try:
            seat = Product.objects.get(slug__in=slugs)
            logger.info('Retrieved [%s] course seat child product for [%s] from database.', certificate_type,
                        course_id)
        except Product.DoesNotExist:
            seat = Product(slug=slug)
            logger.info('[%s] course seat product for [%s] does not exist. Instantiated a new instance.',
                        certificate_type, course_id)

        seat.course = self
        seat.parent = self.parent_seat_product
        seat.is_discountable = True
        seat.structure = Product.CHILD
        seat.title = self._get_course_seat_name(certificate_type, id_verification_required)
        seat.expires = expires
        seat.attr.certificate_type = certificate_type
        seat.attr.course_key = course_id
        seat.attr.id_verification_required = id_verification_required

        if credit_provider:
            seat.attr.credit_provider = credit_provider

        if credit_hours:
            seat.attr.credit_hours = credit_hours

        seat.save()

        # TODO Expose via setting
        partner = Partner.objects.get(code='edx')
        try:
            stock_record = StockRecord.objects.get(product=seat, partner=partner)
            logger.info('Retrieved [%s] course seat child product stock record for [%s] from database.',
                        certificate_type, course_id)
        except StockRecord.DoesNotExist:
            partner_sku = generate_sku(seat)
            stock_record = StockRecord(product=seat, partner=partner, partner_sku=partner_sku)
            logger.info(
                '[%s] course seat product stock record for [%s] does not exist. Instantiated a new instance.',
                certificate_type, course_id)

        stock_record.price_excl_tax = price

        # TODO Expose via setting
        stock_record.price_currency = 'USD'
        stock_record.save()

        return seat
