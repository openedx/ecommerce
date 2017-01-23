""" Custom test decorators. """

import functools

import mock
from django.conf import settings
from edx_rest_api_client.client import EdxRestApiClient


def mock_course_catalog_api_client(test):
    """
    Custom decorator for mocking the course_catalog_api_client property of siteconfiguration
    to return a new instance of EdxRestApiClient with a dummy jwt value.
    """
    def decorate_class(klass):
        for attr in dir(klass):
            # Decorate only callable unit tests.
            if not attr.startswith('test_'):
                continue

            attr_value = getattr(klass, attr)
            if not hasattr(attr_value, "__call__"):
                continue

            setattr(klass, attr, decorate_callable(attr_value))
        return klass

    def decorate_callable(test):
        @functools.wraps(test)
        def wrapper(*args, **kw):
            with mock.patch(
                'ecommerce.core.models.SiteConfiguration.course_catalog_api_client',
                mock.PropertyMock(return_value=EdxRestApiClient(
                    settings.COURSE_CATALOG_API_URL,
                    jwt='auth-token'
                ))
            ):
                return test(*args, **kw)
        return wrapper

    if isinstance(test, type):
        return decorate_class(test)
    return decorate_callable(test)


def mock_enterprise_api_client(test):
    """
    Custom decorator for mocking the property "enterprise_api_client" of
    siteconfiguration to construct a new instance of EdxRestApiClient with a
    dummy jwt value.
    """
    def decorate_class(klass):
        for attr in dir(klass):
            # Decorate only callable unit tests.
            if not attr.startswith('test_'):
                continue

            attr_value = getattr(klass, attr)
            if not hasattr(attr_value, '__call__'):
                continue

            setattr(klass, attr, decorate_callable(attr_value))
        return klass

    def decorate_callable(test):
        @functools.wraps(test)
        def wrapper(*args, **kw):
            with mock.patch(
                'ecommerce.core.models.SiteConfiguration.enterprise_api_client',
                mock.PropertyMock(
                    return_value=EdxRestApiClient(
                        settings.ENTERPRISE_API_URL,
                        jwt='auth-token'
                    )
                )
            ):
                return test(*args, **kw)
        return wrapper

    if isinstance(test, type):
        return decorate_class(test)
    return decorate_callable(test)
