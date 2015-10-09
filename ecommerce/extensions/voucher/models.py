import uuid
from django.db import models, transaction
from django.utils import timezone
from oscar.apps.voucher.abstract_models import AbstractVoucher


class Voucher(AbstractVoucher):
    course_id = models.ForeignKey('courses.Course', null=True, related_name='course')
    discount = models.IntegerField(default=100)
    enrollment_code = models.CharField(null=True, unique=True, max_length=255)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(null=True)
    total_price = models.FloatField(null=True, default=0)

    def generate_code(self):
        return uuid.uuid4().hex[:6].lower()

    @transaction.atomic
    def save(self, *args, **kwargs):  # pylint: disable=bad-super-call
        self.created_at = timezone.now()
        self.enrollment_code = self.generate_code()
        return super(Voucher, self).save(*args, **kwargs)


from oscar.apps.voucher.models import *  # noqa
