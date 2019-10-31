from __future__ import absolute_import

import pytest


@pytest.fixture
def selenium(selenium):  # pylint: disable=redefined-outer-name
    selenium.implicitly_wait(10)
    return selenium


@pytest.fixture
def firefox_options(firefox_options):  # pylint: disable=redefined-outer-name
    firefox_options.set_headless(True)
    return firefox_options
