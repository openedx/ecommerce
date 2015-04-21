ecommerce  |Travis|_ |Coveralls|_
=================================
.. |Travis| image:: https://travis-ci.org/edx/ecommerce.svg?branch=master
.. _Travis: https://travis-ci.org/edx/ecommerce

.. |Coveralls| image:: https://coveralls.io/repos/edx/ecommerce/badge.svg?branch=master
.. _Coveralls: https://coveralls.io/r/edx/ecommerce?branch=master

Overview
--------

This repository contains the edX ecommerce service, which relies heavily on `django-oscar <https://github.com/edx/django-oscar>`_. This repository is home to all front-end and back-end code used to manage edX's product catalog and handle orders for those products, and houses extensions of the Oscar core which are specific to edX's needs. Many of the models in this project override abstract models present in Oscar.

Getting Started
---------------

Most commands necessary to run and develop the ecommerce service can be found in the included Makefile.

To install requirements necessary for local development, run::

    $ make requirements

``requirements/production.txt`` will install the packages needed to run the ecommerce service in a production setting.

To apply migrations, run::
    
    $ make migrations

Setup countries (for addresses) using the following command::

    $ python manage.py oscar_populate_countries

To stand up the development server, run::

    $ make serve

By default, the Django Debug Toolbar is disabled. To enable it, set the ENABLE_DJANGO_TOOLBAR environment variable.

Testing
-------

To run the unit test suite followed by quality checks, run::

    $ make validate

Acceptance tests require a valid LMS configuration and a user with a known username, email address, password, and access token. The following command will run the acceptance tests::

    $ APP_SERVER_URL="<ECOMMERCE-URL>" LMS_URL="<LMS-URL>" LMS_USERNAME="<USERNAME>" LMS_EMAIL="<EMAIL>" LMS_PASSWORD="<PASSWORD>" ACCESS_TOKEN="<ACCESS-TOKEN>" make accept

Note: Access tokens can be generated/obtained from the LMS admin portal (http://127.0.0.1:8000/admin/oauth2/accesstoken/).

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
