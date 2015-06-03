from decimal import Decimal

from django.conf import settings
from django.utils.text import slugify
import factory
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.newfactories import UserFactory

from ecommerce.extensions.refund.status import REFUND, REFUND_LINE

Category = get_model("catalogue", "Category")
Partner = get_model('partner', 'Partner')
Product = get_model("catalogue", "Product")
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


class RefundFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_STATUS', REFUND.OPEN)
    user = factory.SubFactory(UserFactory)
    total_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order(self):
        return factories.create_order(user=self.user)

    @factory.post_generation
    def create_lines(self, create, extracted, **kwargs):    # pylint: disable=unused-argument
        if not create:
            return

        for line in self.order.lines.all():
            RefundLineFactory.create(refund=self, order_line=line)

        self.total_credit_excl_tax = sum([line.line_credit_excl_tax for line in self.lines.all()])
        self.save()

    class Meta(object):
        model = get_model('refund', 'Refund')


class RefundLineFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_LINE_STATUS', REFUND_LINE.OPEN)
    refund = factory.SubFactory(RefundFactory)
    line_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order_line(self):
        order = factories.create_order()
        return order.lines.first()

    class Meta(object):
        model = get_model('refund', 'RefundLine')


class CourseFactory(object):
    def __init__(self, course_id, course_name):
        self.course_name = course_name
        self.course_id = course_id
        self.modes = {}
        self.partner, _created = Partner.objects.get_or_create(name='edX')

    def _get_parent_seat_product(self):
        seat, created = ProductClass.objects.get_or_create(slug='seat',
                                                           defaults={'track_stock': False, 'requires_shipping': False,
                                                                     'name': 'Seat'})

        if created:
            ProductAttribute.objects.create(product_class=seat, name='course_key', code='course_key', type='text',
                                            required=True)
            ProductAttribute.objects.create(product_class=seat, name='id_verification_required',
                                            code='id_verification_required', type='boolean', required=False)
            ProductAttribute.objects.create(product_class=seat, name='certificate_type', code='certificate_type',
                                            type='text', required=False)

        slug = slugify(self.course_name)
        title = u'Seat in {}'.format(self.course_name)
        parent_product, created = Product.objects.get_or_create(product_class=seat, slug=slug, structure='parent',
                                                                defaults={'title': title})
        if created:
            parent_product.attr.course_key = self.course_id
            parent_product.save()

        return parent_product

    def add_mode(self, name, price, id_verification_required=False):
        parent_product = self._get_parent_seat_product()

        title = u'{mode_name} Seat in {course_name}'.format(mode_name=name, course_name=self.course_name)
        slug = slugify(u'{course_name}-seat-{mode_name}'.format(course_name=self.course_name, mode_name=name))
        child_product, created = Product.objects.get_or_create(parent=parent_product, title=title, slug=slug,
                                                               structure='child')

        if created:
            child_product.attr.course_key = self.course_id
            child_product.attr.certificate_type = name
            child_product.attr.id_verification_required = id_verification_required
            child_product.save()

            child_product.stockrecords.create(partner=self.partner, partner_sku=slug, num_in_stock=None,
                                              price_currency=settings.OSCAR_DEFAULT_CURRENCY, price_excl_tax=price)

        self.modes[name] = child_product

        return child_product
