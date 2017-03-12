# -*- coding: utf-8 -*-

from django.template import Context, Template, TemplateSyntaxError

from ecommerce.tests.testcases import TestCase


class CoreExtrasTests(TestCase):
    def test_settings_value(self):
        template = Template(
            "{% load core_extras %}"
            "{% settings_value \"FAKE_SETTING\" %}"
        )

        # If setting is not found, tag should raise an error.
        self.assertRaises(AttributeError, template.render, Context())

        with self.settings(FAKE_SETTING='edX'):
            # If setting is found, tag simply displays setting value.
            self.assertEqual(template.render(Context()), "edX")

    def assertTextCaptured(self, expected):
        template = Template(
            "{% load core_extras %}"
            "{% captureas foo %}{{ expected }}{%endcaptureas%}"
            "{{ foo }}"
        )
        # Tag should render the value captured in the block.
        self.assertEqual(template.render(Context({'expected': expected})), expected)

    def test_captureas(self):
        # Tag requires a variable name.
        self.assertRaises(TemplateSyntaxError, Template,
                          "{% load core_extras %}" "{% captureas %}42{%endcaptureas%}")

        self.assertTextCaptured('42')

    def test_captureas_unicode(self):
        self.assertTextCaptured(u'★❤')

    def test_course_organization(self):
        course_id = 'course-v1:edX+Course+100'
        template = Template(
            "{% load core_extras %}"
            "{{ course_id|course_organization }}"
        )
        self.assertEqual(template.render(Context({'course_id': course_id})), 'edX')
