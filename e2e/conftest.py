

import pytest


@pytest.fixture
def chrome_options(chrome_options):  # pylint: disable=redefined-outer-name
    chrome_options.set_headless(True)
    return chrome_options
