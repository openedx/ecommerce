import __builtin__
import sys
from StringIO import StringIO

import ddt
from mock import patch

from ecommerce.tests.testcases import TestCase

from ..prompt import query_yes_no


@ddt.ddt
class PromptTests(TestCase):
    """Tests for prompt."""

    CONFIRMATION_PROMPT = u'Do you want to continue?'

    def test_wrong_default(self):
        """Test that query_yes_no raises ValueError with wrong default."""
        with self.assertRaises(ValueError):
            query_yes_no(self.CONFIRMATION_PROMPT, default='wrong')

    def test_wrong_user_input(self):
        """Test wrong user input."""
        out = StringIO()
        sys.stdout = out
        with patch.object(__builtin__, 'raw_input', side_effect=['wrong', 'no']):
            query_yes_no(self.CONFIRMATION_PROMPT)
            output = out.getvalue().strip()
            self.assertIn("Please respond with one of the following (y, yes, n, no)", output)

    @patch.object(__builtin__, 'raw_input')
    @ddt.data(
        ('yes', True, 'no'), ('no', False, 'yes'), ('', True, 'yes'), ('yes', True, None)
    )
    @ddt.unpack
    def test_query_yes_no(self, user_input, return_value, default, mock_raw_input):
        """Test that query_yes_no works as expected."""
        mock_raw_input.return_value = user_input
        expected_value = query_yes_no(self.CONFIRMATION_PROMPT, default=default)
        if return_value:
            self.assertTrue(expected_value)
        else:
            self.assertFalse(expected_value)
