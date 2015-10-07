from django.db import models, transaction
from django.utils import timezone


class EnrollmentCode(models.Model):
    course_id = models.CharField(null=False, max_length=255)
    code = models.CharField(null=False, max_length=255)
    price = models.IntegerField()
    created_by_id = models.ForeignKey('core.User')
    created_at = models.DateTimeField()
    order_id = models.ForeignKey('order.Order')

    @transaction.atomic
    def save(self, *args, **kwargs):  # pylint: disable=bad-super-call
        self.created_at = timezone.now()
        return super(EnrollmentCode, self).save(*args, **kwargs)
