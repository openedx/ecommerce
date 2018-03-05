from django.db.models import CharField, Model
from django_mysql.models import ListCharField
from django.utils.translation import ugettext_lazy as _
from uuid import uuid4

class Bundle(Model):
    uuid = models.UUIDField(blank=True, default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    title = models.CharField(
        help_text=_('The user-facing display title for this Bundle.'),
        max_length=255,
        unique=True
    )
    course_ids = ListCharField(
        base_field=CharField(max_length=10),
        size=6,
        max_length=(6 * 11)  # 6 * 10 character nominals, plus commas
    )
