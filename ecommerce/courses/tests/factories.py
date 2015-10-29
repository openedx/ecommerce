import factory

from ecommerce.courses.models import Course


class CourseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Course
