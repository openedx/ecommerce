class DashboardViewTestMixin(object):
    def assert_message_equals(self, response, msg, level):  # pylint: disable=unused-argument
        """ Verify the latest message matches the expected value. """
        messages = []
        for context in response.context:
            messages += context.get('messages', [])

        message = messages[0]
        self.assertEqual(message.level, level)
        self.assertEqual(message.message, msg)
