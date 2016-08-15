# encoding: utf-8
"""Contains the tests for populate organization in existing courses command."""

from __future__ import unicode_literals

import ddt
from django.core.management import call_command
from django.test import TestCase

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin


@ddt.ddt
class AddCourseOrganizationTests(CourseCatalogTestMixin, TestCase):
    """Tests the add course organization."""

    def setUp(self):
        super(AddCourseOrganizationTests, self).setUp()
        self.course = CourseFactory()
        self.course_org = 'test-org'

    def test_add_course_organization(self):
        """ Verify add course organization. """
        course = CourseFactory.create()
        self.assertEqual(course.organization, '')

        call_command('add_course_organization')
        course = Course.objects.filter(id=self.course.id).first()
        self.assertEqual(course.organization, 'test-org')
