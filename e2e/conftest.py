import pytest


@pytest.fixture
def selenium(selenium):  # pylint: disable=redefined-outer-name
    selenium.implicitly_wait(10)
    return selenium
