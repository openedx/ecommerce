from __future__ import unicode_literals

import logging

import waffle
from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils.timezone import now, timedelta
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class, get_model
from simple_history.models import HistoricalRecords

from ecommerce.core.constants import (
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    ENROLLMENT_CODE_SEAT_TYPES,
    ENROLLMENT_CODE_SWITCH,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.catalogue.utils import generate_sku

logger = logging.getLogger(__name__)
Category = get_model('catalogue', 'Category')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')


class Course(models.Model):
    site = models.ForeignKey('sites.Site', verbose_name=_('Site'), null=False, blank=False, on_delete=models.PROTECT)
    id = models.CharField(null=False, max_length=255, primary_key=True, verbose_name='ID')
    name = models.CharField(null=False, max_length=255)
    verification_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Last date/time on which verification for this product can be submitted.')
    )
    history = HistoricalRecords()
    created = models.DateTimeField(null=True, auto_now_add=True)
    modified = models.DateTimeField(null=True, auto_now=True)
    thumbnail_url = models.URLField(null=True, blank=True)

    def __unicode__(self):
        return unicode(self.id)

    def _create_parent_seat(self):
        """ Create the parent seat product if it does not already exist. """
        parent, created = self.products.get_or_create(
            course=self,
            structure=Product.PARENT,
            product_class=ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME),
        )
        ProductCategory.objects.get_or_create(category=Category.objects.get(name='Seats'), product=parent)
        parent.title = 'Seat in {}'.format(self.name)
        parent.is_discountable = True
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
        elif mode == 'audit':
            # Historically, users enrolled in an 'audit' mode have not received a certificate.
            return ''

        return mode

    @property
    def type(self):
        """ Returns the type of the course (based on the available seat types). """
        seat_types = [getattr(seat.attr, 'certificate_type', '').lower() for seat in self.seat_products]
        if 'credit' in seat_types:
            return 'credit'
        elif 'professional' in seat_types or 'no-id-professional' in seat_types:
            return 'professional'
        elif 'verified' in seat_types:
            return 'verified'
        else:
            return 'audit'

    @property
    def parent_seat_product(self):
        """ Returns the course seat parent Product. """
        return self.products.get(product_class__name=SEAT_PRODUCT_CLASS_NAME, structure=Product.PARENT)

    @property
    def seat_products(self):
        """ Returns a queryset of course seat Products related to this course. """
        return self.parent_seat_product.children.all().prefetch_related('stockrecords')

    @property
    def enrollment_code_product(self):
        """Returns this course's enrollment code if it exists and is active."""
        enrollment_code = self.get_enrollment_code()
        if enrollment_code:
            info = Selector().strategy().fetch_for_product(enrollment_code)
            if info.availability.is_available_to_buy:
                return enrollment_code
        return None

    @property
    def partner(self):
        return self.site.siteconfiguration.partner

    def get_course_seat_name(self, certificate_type, id_verification_required):
        """ Returns the name for a course seat. """
        name = u'Seat in {}'.format(self.name)

        if certificate_type != '':
            name += u' with {} certificate'.format(certificate_type)

            if id_verification_required:
                name += u' (and ID verification)'

        return name

    def create_or_update_seat(
            self,
            certificate_type,
            id_verification_required,
            price,
            partner,
            credit_provider=None,
            expires=None,
            credit_hours=None,
            remove_stale_modes=True,
            create_enrollment_code=False
    ):
        """
        Creates course seat products.

        Arguments:
            certificate_type(str): The seat type.
            id_verification_required(bool): Whether an ID verification is required.
            price(int): Price of the seat.
            partner(Partner): Site partner.

        Optional arguments:
            credit_provider(str): Name of the organization that provides the credit
            expires(datetime): Date when the seat type expires.
            credit_hours(int): Number of credit hours provided.
            remove_stale_modes(bool): Remove stale modes.
            create_enrollment_code(bool): Whether an enrollment code is created in addition to the seat.

        Returns:
            Product:  The seat that has been created or updated.
        """
        certificate_type = certificate_type.lower()
        course_id = unicode(self.id)

        if certificate_type == self.certificate_type_for_mode('audit'):
            # Yields a match if attribute names do not include 'certificate_type'.
            certificate_type_query = ~Q(attributes__name='certificate_type')
        else:
            # Yields a match if attribute with name 'certificate_type' matches provided value.
            certificate_type_query = Q(
                attributes__name='certificate_type',
                attribute_values__value_text=certificate_type
            )

        id_verification_required_query = Q(
            attributes__name='id_verification_required',
            attribute_values__value_boolean=id_verification_required
        )

        if credit_provider is None:
            # Yields a match if attribute names do not include 'credit_provider'.
            credit_provider_query = ~Q(attributes__name='credit_provider')
        else:
            # Yields a match if attribute with name 'credit_provider' matches provided value.
            credit_provider_query = Q(
                attributes__name='credit_provider',
                attribute_values__value_text=credit_provider
            )

        seats = self.seat_products.filter(certificate_type_query)
        try:
            seat = seats.filter(
                id_verification_required_query
            ).get(
                credit_provider_query
            )

            logger.info(
                'Retrieved course seat child product with certificate type [%s] for [%s] from database.',
                certificate_type,
                course_id
            )
        except Product.DoesNotExist:
            seat = Product()
            logger.info(
                'Course seat product with certificate type [%s] for [%s] does not exist. Instantiated a new instance.',
                certificate_type,
                course_id
            )

        seat.course = self
        seat.structure = Product.CHILD
        seat.parent = self.parent_seat_product
        seat.is_discountable = True
        seat.title = self.get_course_seat_name(certificate_type, id_verification_required)
        seat.expires = expires

        seat.save()

        # If a ProductAttribute is saved with a value of None or the empty string, the ProductAttribute is deleted.
        # As a consequence, Seats derived from a migrated "audit" mode do not have a certificate_type attribute.
        seat.attr.certificate_type = certificate_type
        seat.attr.course_key = course_id
        seat.attr.id_verification_required = id_verification_required
        if waffle.switch_is_active(ENROLLMENT_CODE_SWITCH) and \
                certificate_type in ENROLLMENT_CODE_SEAT_TYPES and \
                create_enrollment_code:
            self._create_or_update_enrollment_code(certificate_type, id_verification_required, partner, price, expires)

        if credit_provider:
            seat.attr.credit_provider = credit_provider

        if credit_hours:
            seat.attr.credit_hours = credit_hours

        seat.attr.save()

        try:
            stock_record = StockRecord.objects.get(product=seat, partner=partner)
            logger.info(
                'Retrieved course seat product stock record with certificate type [%s] for [%s] from database.',
                certificate_type,
                course_id
            )
        except StockRecord.DoesNotExist:
            partner_sku = generate_sku(seat, partner)
            stock_record = StockRecord(product=seat, partner=partner, partner_sku=partner_sku)
            logger.info(
                'Course seat product stock record with certificate type [%s] for [%s] does not exist. '
                'Instantiated a new instance.',
                certificate_type,
                course_id
            )

        stock_record.price_excl_tax = price
        stock_record.price_currency = settings.OSCAR_DEFAULT_CURRENCY
        stock_record.save()

        if remove_stale_modes and self.certificate_type_for_mode(certificate_type) == 'professional':
            id_verification_required_query = Q(
                attributes__name='id_verification_required',
                attribute_values__value_boolean=not id_verification_required
            )

            # Delete seats with a different verification requirement, assuming the seats
            # have not been purchased.
            seats.annotate(orders=Count('line')).filter(
                id_verification_required_query,
                orders=0
            ).delete()

        return seat

    def get_enrollment_code(self):
        """ Returns an enrollment code Product related to this course. """
        try:
            # Current use cases dictate that only one enrollment code product exists for a given course
            return Product.objects.get(
                product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
                course=self
            )
        except Product.DoesNotExist:
            return None

    def _create_or_update_enrollment_code(self, seat_type, id_verification_required, partner, price, expires):
        """
        Creates an enrollment code product and corresponding stock record for the specified seat.
        Includes course ID and seat type as product attributes.

        Args:
            seat_type (str): Seat type.
            partner (Partner): Seat provider set in the stock record.
            price (Decimal): Price of the seat.
            expires (datetime): Date when the enrollment code expires.

        Returns:
            Enrollment code product.
        """
        enrollment_code_product_class = ProductClass.objects.get(name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        enrollment_code = self.get_enrollment_code()

        if not enrollment_code:
            title = 'Enrollment code for {seat_type} seat in {course_name}'.format(
                seat_type=seat_type,
                course_name=self.name
            )
            enrollment_code = Product(
                title=title,
                product_class=enrollment_code_product_class,
                course=self,
                expires=expires
            )
        enrollment_code.attr.course_key = self.id
        enrollment_code.attr.seat_type = seat_type
        enrollment_code.attr.id_verification_required = id_verification_required
        enrollment_code.save()

        try:
            stock_record = StockRecord.objects.get(product=enrollment_code, partner=partner)
        except StockRecord.DoesNotExist:
            enrollment_code_sku = generate_sku(enrollment_code, partner)
            stock_record = StockRecord(
                product=enrollment_code,
                partner=partner,
                partner_sku=enrollment_code_sku
            )

        stock_record.price_excl_tax = price
        stock_record.price_currency = settings.OSCAR_DEFAULT_CURRENCY
        stock_record.save()

        return enrollment_code

    def toggle_enrollment_code_status(self, is_active):
        """Activate or deactivate an enrollment code.

        An enrollment code's expiration date should not exceed the accompanying
        seat's expiration date. If the seat does not have an expiration date, the
        enrollment code's expiration date is set to an arbitrary number of days
        in the future (365).

        Args:
            is_active (bool): Whether the enrollment code should be activated.
        """
        enrollment_code = self.get_enrollment_code()
        if enrollment_code:
            if is_active:
                seat = self.seat_products.get(
                    attributes__name='certificate_type',
                    attribute_values__value_text=enrollment_code.attr.seat_type
                )
                enrollment_code.expires = seat.expires if seat.expires else now() + timedelta(days=365)
            else:
                enrollment_code.expires = now() - timedelta(days=365)
            enrollment_code.save()
