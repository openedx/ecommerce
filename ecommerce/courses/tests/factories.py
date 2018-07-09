from __future__ import unicode_literals

import factory
from factory.fuzzy import FuzzyText

from ecommerce.courses.models import Course


class CourseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Course

    id = FuzzyText(prefix='course-v1:test-org+course+')
    name = FuzzyText(prefix='course-name-')
    site = factory.SubFactory('ecommerce.tests.factories.SiteFactory')
    partner = factory.SubFactory('ecommerce.tests.factories.PartnerFactory')
