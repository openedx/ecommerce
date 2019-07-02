"""
Set up for running pytest

Pytest is faster than running `./manage.py test` since it will not create a
database. If a test has database dependencies, that test will not pass.
"""
from __future__ import absolute_import, print_function

import django


def pytest_configure(config):  # pylint: disable=unused-argument
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("! WARNING: Not all tests pass with pytest. Pytest does not create a !\n"
          "! database. If a test has database dependencies, that test will not !\n"
          "! pass.                                                             !")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    django.setup()
