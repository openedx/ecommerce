"""
Set up for running pytest

Pytest is faster than running `./manage.py test` since it will not create a
database. If a test has database dependencies, that test will not pass.
"""
from __future__ import absolute_import, print_function

import pytest


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass
