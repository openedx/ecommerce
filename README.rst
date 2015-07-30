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

Asset Pipeline
--------------
Static files are managed via `django-compressor`_ and `RequireJS`_ (and r.js) are used to manage JavaScript dependencies.
django-compressor compiles SASS, minifies JavaScript, and handles naming files to facilitate cache busting during deployment.

.. _django-compressor: http://django-compressor.readthedocs.org/
.. _RequireJS: http://requirejs.org/

Both tools should operate seamlessly in a local development environment. When deploying to production, call
``make static`` to compile all static assets and move them to the proper location to be served.

When creating new pages that utilize RequireJS dependencies, remember new modules to ``build.js``.

NOTE: The static file directories are setup such that the build output directory of ``r.js`` is read before checking
for assets in ``ecommerce\static\``. If you run ``make static`` or ``r.js`` locally (which you should not need to),
make sure you delete ``ecommerce/static/build`` or run ``make static`` before continuing with development. If you do not
all changes made to static files will be ignored.

Feature Switches
----------------
This app uses `Waffle`_ to manage feature gating/switching. Switches can be managed via Django admin. The following
switches exist:

+--------------------------------+---------------------------------------------------------------------------+
| Name                           | Functionality                                                             |
+================================+=======================+===================================================+
| user_enrollments_on_dashboard  | Display a user's current enrollments on the dashboard user detail page    |
+--------------------------------+---------------------------------------------------------------------------+
| publish_course_modes_to_lms    | Publish prices and SKUs to the LMS after every course modification        |
+--------------------------------+---------------------------------------------------------------------------+
| ENABLE_CREDIT_APP              | Enable the credit checkout page from where student's can purchase credit  |
|                                | courses.                                                                  |
+--------------------------------+---------------------------------------------------------------------------+

.. _Waffle: https://waffle.readthedocs.org/


Analytics
---------

To use google analytics for specific events e.g., button clicks, you need to add the segment key into the settings
file:

``SEGMENT_KEY = 'your segment key'``


Credit
------

To enable custom credit checkout page, please add the following waffle switch:

``ENABLE_CREDIT_APP``


Testing
-------

To run the unit test suite followed by quality checks, run::

    $ make validate

To run only Python unit tests, run:

::

    $ make test_python

To run only JavaScript unit tests, run:

::

    $ make test_javascript

JavaScript Unit Testing
~~~~~~~~~~~~~~~~~~~~~~~

JavaScript is unit tested using the Jasmine framework and should follow the `Jasmine 2.3 API
specifications <http://jasmine.github.io/2.3/introduction.html>`__.
Tests should be placed in the ecommerce/static/js/test/specs directory, and suffixed with _spec
(e.g. ecommerce/static/js/test/specs/course_list_view_spec.js).

Tests can be run with the following command:

::

    $ make test_javascript

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
