from django.db import models
from django.utils import timezone


class EnrollmentCode(models.Model):
    course_id = models.CharField(null=False, max_length=255)
    code = models.CharField(null=False, max_length=255)
    price = models.IntegerField()
    created_by_id = models.ForeignKey('core.User')
    created_at = models.DateTimeField()
    order_id = models.ForeignKey('extensions.order.Order')

    def save(self, *args, **kwargs):
        self.created_at = timezone.now()
        return super(EnrollmentCode, self).save(*args, **kwargs)
