import pytest


@pytest.fixture
def selenium(selenium):  # pylint: disable=redefined-outer-name
    selenium.implicitly_wait(10)
    return selenium


@pytest.fixture
def chrome_options(chrome_options):
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return chrome_options
