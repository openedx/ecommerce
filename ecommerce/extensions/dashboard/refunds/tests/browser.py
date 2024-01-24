"""
Use environment variables to configure Selenium remote WebDriver.
For use with SauceLabs (via SauceConnect) or local browsers.
"""

import logging
import os

try:
    from needle.driver import NeedleChrome as Chrome
    from needle.driver import NeedleFirefox as Firefox
    from needle.driver import NeedleIe as Ie
    from needle.driver import NeedleOpera as Opera
    from needle.driver import NeedlePhantomJS as PhantomJS
    from needle.driver import NeedleSafari as Safari
except ImportError:
    from selenium.webdriver import Chrome, Firefox, Ie, Opera, PhantomJS, Safari

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from ecommerce.extensions.dashboard.refunds.tests.promise import Promise

LOGGER = logging.getLogger(__name__)

REMOTE_ENV_VARS = [
    'SELENIUM_BROWSER',
    'SELENIUM_HOST',
    'SELENIUM_PORT',
]

SAUCE_ENV_VARS = REMOTE_ENV_VARS + [
    'SELENIUM_VERSION',
    'SELENIUM_PLATFORM',
    'SAUCE_USER_NAME',
    'SAUCE_API_KEY',
]


OPTIONAL_ENV_VARS = [
    'JOB_NAME',
    'BUILD_NUMBER',
    'SELENIUM_INSECURE_CERTS',
]


BROWSERS = {
    'chrome': Chrome,
    'firefox': Firefox,
    'internet explorer': Ie,
    'opera': Opera,
    'phantomjs': PhantomJS,
    'safari': Safari,
}


class BrowserConfigError(Exception):

    """
    Misconfiguration error in the environment variables.
    """


def browser(tags=None, proxy=None, other_caps=None):
    """
    Interpret environment variables to configure Selenium.
    Performs validation, logging, and sensible defaults.

    There are three cases:

    1. Local browsers: If the proper environment variables are not all set for the second case,
        then we use a local browser.

        * The environment variable `SELENIUM_BROWSER` can be set to specify which local browser to use. The default is \
          Firefox.
        * Additionally, if a proxy instance is passed and the browser choice is either Chrome or Firefox, then the \
          browser will be initialized with the proxy server set.
        * The environment variable `SELENIUM_FIREFOX_PATH` can be used for specifying a path to the Firefox binary. \
          Default behavior is to use the system location.
        * The environment variable `FIREFOX_PROFILE_PATH` can be used for specifying a path to the Firefox profile. \
          Default behavior is to use a barebones default profile with a few useful preferences set.

    2. Remote browser (not SauceLabs): Set all of the following environment variables, but not all of
        the ones needed for SauceLabs:

        * SELENIUM_BROWSER
        * SELENIUM_HOST
        * SELENIUM_PORT

    3. SauceLabs: Set all of the following environment variables:

        * SELENIUM_BROWSER
        * SELENIUM_VERSION
        * SELENIUM_PLATFORM
        * SELENIUM_HOST
        * SELENIUM_PORT
        * SAUCE_USER_NAME
        * SAUCE_API_KEY

    **NOTE:** these are the environment variables set by the SauceLabs
    Jenkins plugin.

    Optionally provide Jenkins info, used to identify jobs to Sauce:

        * JOB_NAME
        * BUILD_NUMBER

    `tags` is a list of string tags to apply to the SauceLabs
    job.  If not using SauceLabs, these will be ignored.

    Keyword Args:
        tags (list of str): Tags to apply to the SauceLabs job.  If not using SauceLabs, these will be ignored.
        proxy: A proxy instance.
        other_caps (dict of str): Additional desired capabilities to provide to remote WebDriver instances. Note
        that these values will be overwritten by environment variables described above. This is only used for
        remote driver instances, where such info is usually used by services for additional configuration and
        metadata.

    Returns:
        selenium.webdriver: The configured browser object used to drive tests

    Raises:
        BrowserConfigError: The environment variables are not correctly specified.
    """

    browser_name = os.environ.get('SELENIUM_BROWSER', 'firefox')

    def browser_check_func():
        """ Instantiate the browser and return the browser instance """
        # See https://openedx.atlassian.net/browse/TE-701
        try:
            # Get the class and kwargs required to instantiate the browser based on
            # whether we are using a local or remote one.
            if _use_remote_browser(SAUCE_ENV_VARS):
                browser_class, browser_args, browser_kwargs = _remote_browser_class(
                    SAUCE_ENV_VARS, tags)
            elif _use_remote_browser(REMOTE_ENV_VARS):
                browser_class, browser_args, browser_kwargs = _remote_browser_class(
                    REMOTE_ENV_VARS, tags)
            else:
                browser_class, browser_args, browser_kwargs = _local_browser_class(
                    browser_name)

            # If we are using a proxy, we need extra kwargs passed on intantiation.
            if proxy:
                browser_kwargs = _proxy_kwargs(browser_name, proxy, browser_kwargs)

            # Load in user given desired caps but override with derived caps from above. This is to retain existing
            # behavior. Only for remote drivers, where various testing services use this info for configuration.
            if browser_class == webdriver.Remote:
                desired_caps = other_caps or {}
                desired_caps.update(browser_kwargs.get('desired_capabilities', {}))
                browser_kwargs['desired_capabilities'] = desired_caps

            return True, browser_class(*browser_args, **browser_kwargs)

        except (OSError, WebDriverException) as err:
            msg = str(err)
            LOGGER.debug('Failed to instantiate browser: %s', msg)
            return False, None

    browser_instance = Promise(
        # There are cases where selenium takes 30s to return with a failure, so in order to try 3
        # times, we set a long timeout. If there is a hang on the first try, the timeout will
        # be enforced.
        browser_check_func, "Browser is instantiated successfully.", try_limit=3, timeout=95).fulfill()

    return browser_instance


def _local_browser_class(browser_name):
    """
    Returns class, kwargs, and args needed to instantiate the local browser.
    """

    # Log name of local browser
    LOGGER.info("Using local browser: %s [Default is firefox]", browser_name)

    # Get class of local browser based on name
    browser_class = BROWSERS.get(browser_name)
    if browser_class is None:
        raise BrowserConfigError(
            f"Invalid browser name {browser_name}.  Options are: {', '.join(list(BROWSERS.keys()))}"
        )

    if browser_name == 'firefox':
        # Remove geckodriver log data from previous test cases
        log_path = os.path.join(os.getcwd(), 'geckodriver.log')
        if os.path.exists(log_path):
            os.remove(log_path)

        firefox_options = FirefoxOptions()
        firefox_options.log.level = 'trace'
        firefox_options.headless = True
        browser_args = []
        browser_kwargs = {
            'options': firefox_options,
        }

        firefox_path = os.environ.get('SELENIUM_FIREFOX_PATH')
        firefox_log = os.environ.get('SELENIUM_FIREFOX_LOG')
        if firefox_path and firefox_log:
            browser_kwargs.update({
                'firefox_binary': FirefoxBinary(
                    firefox_path=firefox_path, log_file=firefox_log)
            })
        elif firefox_path:
            browser_kwargs.update({
                'firefox_binary': FirefoxBinary(firefox_path=firefox_path)
            })
        elif firefox_log:
            browser_kwargs.update({
                'firefox_binary': FirefoxBinary(log_file=firefox_log)
            })

    elif browser_name == 'chrome':
        chrome_options = ChromeOptions()
        chrome_options.headless = True

        # Emulate webcam and microphone for testing purposes
        chrome_options.add_argument('--use-fake-device-for-media-stream')

        # Bypasses the security prompt displayed by the browser when it attempts to
        # access a media device (e.g., a webcam)
        chrome_options.add_argument('--use-fake-ui-for-media-stream')
        browser_args = []
        browser_kwargs = {
            'options': chrome_options,
        }
    else:
        browser_args, browser_kwargs = [], {}
    return browser_class, browser_args, browser_kwargs


def _remote_browser_class(env_vars, tags=None):
    """
    Returns class, kwargs, and args needed to instantiate the remote browser.
    """
    if tags is None:
        tags = []

    # Interpret the environment variables, raising an exception if they're
    # invalid
    envs = _required_envs(env_vars)
    envs.update(_optional_envs())

    # Turn the environment variables into a dictionary of desired capabilities
    caps = _capabilities_dict(envs, tags)

    if 'accessKey' in caps:
        LOGGER.info("Using SauceLabs: %s %s %s", caps['platform'], caps['browserName'], caps['version'])
    else:
        LOGGER.info("Using Remote Browser: %s", caps['browserName'])

    # Create and return a new Browser
    # We assume that the WebDriver end-point is running locally (e.g. using
    # SauceConnect)
    url = f"http://{envs['SELENIUM_HOST']}:{envs['SELENIUM_PORT']}/wd/hub"

    browser_args = []
    browser_kwargs = {
        'command_executor': url,
        'desired_capabilities': caps,
    }

    return webdriver.Remote, browser_args, browser_kwargs


def _proxy_kwargs(browser_name, proxy, browser_kwargs={}):  # pylint: disable=dangerous-default-value
    """
    Determines the kwargs needed to set up a proxy based on the
    browser type.

    Returns: a dictionary of arguments needed to pass when
        instantiating the WebDriver instance.
    """

    proxy_dict = {
        "httpProxy": proxy.proxy,
        "proxyType": 'manual',
    }

    if browser_name == 'firefox' and 'desired_capabilities' not in browser_kwargs:
        # This one works for firefox locally
        wd_proxy = webdriver.common.proxy.Proxy(proxy_dict)
        browser_kwargs['proxy'] = wd_proxy
    else:
        # This one works with chrome, both locally and remote
        # This one works with firefox remote, but not locally
        if 'desired_capabilities' not in browser_kwargs:
            browser_kwargs['desired_capabilities'] = {}

        browser_kwargs['desired_capabilities']['proxy'] = proxy_dict

    return browser_kwargs


def _use_remote_browser(required_vars):
    """
    Returns a boolean indicating whether we should use a remote
    browser.  This means the user has made an attempt to set
    environment variables indicating they want to connect to SauceLabs
    or a remote browser.
    """
    return all(
        key in os.environ
        for key in required_vars
    )


def _required_envs(env_vars):
    """
    Parse environment variables for required values,
    raising a `BrowserConfig` error if they are not found.

    Returns a `dict` of environment variables.
    """
    envs = {
        key: os.environ.get(key)
        for key in env_vars
    }

    # Check for missing keys
    missing = [key for key, val in list(envs.items()) if val is None]
    if missing:
        msg = (
            "These environment variables must be set: " + ", ".join(missing)
        )
        raise BrowserConfigError(msg)

    # Check that we support this browser
    if envs['SELENIUM_BROWSER'] not in BROWSERS:
        msg = f"Unsuppported browser: {envs['SELENIUM_BROWSER']}"
        raise BrowserConfigError(msg)

    return envs


def _optional_envs():
    """
    Parse environment variables for optional values,
    raising a `BrowserConfig` error if they are insufficiently specified.

    Returns a `dict` of environment variables.
    """
    envs = {
        key: os.environ.get(key)
        for key in OPTIONAL_ENV_VARS
        if key in os.environ
    }

    # If we're using Jenkins, check that we have all the required info
    if 'JOB_NAME' in envs and 'BUILD_NUMBER' not in envs:
        raise BrowserConfigError("Missing BUILD_NUMBER environment var")

    if 'BUILD_NUMBER' in envs and 'JOB_NAME' not in envs:
        raise BrowserConfigError("Missing JOB_NAME environment var")

    return envs


def _capabilities_dict(envs, tags):
    """
    Convert the dictionary of environment variables to
    a dictionary of desired capabilities to send to the
    Remote WebDriver.

    `tags` is a list of string tags to apply to the SauceLabs job.
    """
    capabilities = {
        'browserName': envs['SELENIUM_BROWSER'],
        'acceptInsecureCerts': bool(envs.get('SELENIUM_INSECURE_CERTS', False)),
        'video-upload-on-pass': False,
        'sauce-advisor': False,
        'capture-html': True,
        'record-screenshots': True,
        'max-duration': 600,
        'public': 'public restricted',
        'tags': tags,
    }

    # Add SauceLabs specific environment vars if they are set.
    if _use_remote_browser(SAUCE_ENV_VARS):
        sauce_capabilities = {
            'platform': envs['SELENIUM_PLATFORM'],
            'version': envs['SELENIUM_VERSION'],
            'username': envs['SAUCE_USER_NAME'],
            'accessKey': envs['SAUCE_API_KEY'],
        }

        capabilities.update(sauce_capabilities)

    # Optional: Add in Jenkins-specific environment variables
    # to link Sauce output with the Jenkins job
    if 'JOB_NAME' in envs:
        jenkins_vars = {
            'build': envs['BUILD_NUMBER'],
            'name': envs['JOB_NAME'],
        }

        capabilities.update(jenkins_vars)

    return capabilities
