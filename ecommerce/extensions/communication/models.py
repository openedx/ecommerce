from oscar.apps.communication.models import *  # pylint: disable=wildcard-import,unused-wildcard-import # noqa isort:skip
from django.db import models


class UserLearnerAssessmentDataTranslationAuditDepartment(models.Model):
    user_id_abc_def = models.PositiveIntegerField(blank=False, null=False, db_index=True)
