
from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.extensions.offer.constants import DAY19
from ecommerce.tests.testcases import TestCase

CodeAssignmentNudgeEmailTemplates = get_model('offer', 'CodeAssignmentNudgeEmailTemplates')


class UpdateNudgeEmailSubjectTests(TestCase):
    """Tests for update_nudge_email_subject management command."""

    def test_command(self):
        """Test that command updates the subject to it's correct value."""
        email_template, _ = CodeAssignmentNudgeEmailTemplates.objects.update_or_create(
            email_type=DAY19,
            defaults={
                'email_greeting': 'Test Greeting',
                'email_closing': 'Test Closing',
                'email_subject': 'Wrong Value!',
                'name': 'Test Name',
            }
        )

        call_command('update_nudge_email_subject')
        email_template = CodeAssignmentNudgeEmailTemplates.objects.get(email_type=DAY19)

        assert email_template.email_subject == "It's not too late to redeem your edX code!"
