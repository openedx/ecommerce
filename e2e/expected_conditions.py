"""Expectations for use with Selenium's WebDriverWait."""


class option_selected(object):
    """An expectation for checking that an option has been selected."""
    def __init__(self, select, text):
        self.select = select
        self.text = text

    def __call__(self, _):
        return self.select.first_selected_option.text == self.text


class input_provided(object):
    """An expectation for checking that input values have been provided."""
    def __init__(self, *elements):
        self.elements = elements

    def __call__(self, _):
        return all([element.get_attribute('value') for element in self.elements])
