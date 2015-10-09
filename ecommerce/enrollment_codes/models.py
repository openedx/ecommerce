from django.db import models, transaction
from django.utils import timezone


class EnrollmentCode(models.Model):
    course = models.ForeignKey('courses.Course', null=False, related_name='course')
    voucher = models.ForeignKey('voucher.Voucher', null=True, related_name='voucher')
    created_at = models.DateTimeField()
    author_id = models.ForeignKey('core.User', null=False)
    discount = models.IntegerField(default=100)

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.created_at = timezone.now()
        if self.voucher:
            self.discount = self.voucher.total_discount
        return super(EnrollmentCode, self).save(*args, **kwargs)


