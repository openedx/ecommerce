import uuid
from django.db import models, transaction
from django.utils import timezone


class EnrollmentCode(models.Model):
    enrollment_code = models.CharField(null=False, max_length=255, default='')
    course = models.ForeignKey('courses.Course', null=False, related_name='course')
    voucher = models.ForeignKey('voucher.Voucher', null=True, related_name='voucher')
    created_at = models.DateTimeField()
    author_id = models.ForeignKey('core.User', null=False)
    discount = models.IntegerField(default=100)

    def __unicode__(self):
        return unicode(self.course), ' - ', unicode(self.enrollment_code)

    def generate_code(self):
        return uuid.uuid4().hex[:6].lower()

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.created_at = timezone.now()
        # If there is a voucher added use the discount value
        # of that voucher instead
        if self.voucher:
            self.discount = int(self.voucher.benefit.value)
        self.enrollment_code = self.generate_code()
        return super(EnrollmentCode, self).save(*args, **kwargs)
