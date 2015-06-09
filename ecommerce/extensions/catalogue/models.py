# noinspection PyUnresolvedReferences
from django.db import models
from oscar.apps.catalogue.abstract_models import AbstractProduct


class Product(AbstractProduct):
    course = models.ForeignKey('courses.Course', null=True, blank=True, related_name='products')

# noinspection PyUnresolvedReferences
from oscar.apps.catalogue.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
