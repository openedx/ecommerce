

import pytest


@pytest.fixture
def selenium(selenium):  # pylint: disable=redefined-outer-name
    selenium.implicitly_wait(10)
    return selenium


@pytest.fixture
def chrome_options(chrome_options):  # pylint: disable=redefined-outer-name
    chrome_options.set_headless(True)
    return chrome_options
