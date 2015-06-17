edX E-Commerce Service  |Travis|_ |Coveralls|_
==============================================
.. |Travis| image:: https://travis-ci.org/edx/ecommerce.svg?branch=master
.. _Travis: https://travis-ci.org/edx/ecommerce

.. |Coveralls| image:: https://coveralls.io/repos/edx/ecommerce/badge.svg?branch=master
.. _Coveralls: https://coveralls.io/r/edx/ecommerce?branch=master

This repository contains the edX E-Commerce Service, which relies heavily on `django-oscar <https://github.com/edx/django-oscar>`_, as well as all frontend and backend code used to manage edX's product catalog and handle orders for those products.

Prerequisites
-------------
* Python 2.7.x (not tested with Python 3.x)
* `gettext <http://www.gnu.org/software/gettext/>`_
* `npm <https://www.npmjs.org/>`_

Getting Started
---------------

Most commands necessary to run and develop the ecommerce service can be found in the included Makefile.

1. Install the Python/Node/Bower requirements for local development::

    $ make requirements

Note: If you want to install only the production requirements run ``pip install -r requirements/production.txt``.

2. Setup the database::
    
    $ make migrate

3. Populate the countries tables (used for storing addresses)::

    $ python manage.py oscar_populate_countries

4. Run the development server::

    $ make serve

Django Debug Toolbar is disabled by default. Enable it by setting the environment variable ENABLE_DJANGO_TOOLBAR.

Alternatively, you can launch the server using:

    $ ENABLE_DJANGO_TOOLBAR=1 make serve

Testing
-------

To run the unit test suite followed by quality checks, run::

    $ make validate

Acceptance Testing
~~~~~~~~~~~~~~~~~~

For instructions on how to run the acceptance tests, please consult the
README file located in the `acceptance tests README`_.

.. _acceptance tests README: acceptance_tests/README.rst

Documentation |ReadtheDocs|_ 
----------------------------
.. |ReadtheDocs| image:: https://readthedocs.org/projects/edx-ecommerce/badge/?version=latest
.. _ReadtheDocs: http://edx-ecommerce.readthedocs.org/en/latest/

License
-------

The code in this repository is licensed under the AGPL unless otherwise noted. Please see ``LICENSE.txt`` for details.

How To Contribute
-----------------

Contributions are welcome. Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details. Even though it was written with ``edx-platform`` in mind, these guidelines should be followed for Open edX code in general.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Mailing List and IRC Channel
----------------------------

You can discuss this code on the `edx-code Google Group <https://groups.google.com/forum/#!forum/edx-code>`_ or in the ``#edx-code`` IRC channel on Freenode.
