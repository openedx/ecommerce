ecommerce  |Travis|_ |Coveralls|_
=================================
.. |Travis| image:: https://travis-ci.org/edx/ecommerce.svg?branch=master
.. _Travis: https://travis-ci.org/edx/ecommerce

.. |Coveralls| image:: https://coveralls.io/repos/edx/ecommerce/badge.svg?branch=master
.. _Coveralls: https://coveralls.io/r/edx/ecommerce?branch=master

The edX E-Commerce Front End Service. This repository is the new home for all
front-end code related to products, purchasing, upsell, and marketing.

This project is new and under active development.

Overview
--------

This service contains the front end for all views related to products and
purchasable services offered by edX. All business logic and underlying
applications are invoked separately from other edX projects, such as
edx-platform. The e-commerce solution responsible for all purchases and
transactions is `django-oscar <https://github.com/edx/django-oscar>`_.

Each top level application in this repository is an isolated set of views
specific to one aspect of edX's e-commerce solution.

Getting Started
---------------

By default the Django Default Toolbar is disabled. To enable it, set the environmental variable ENABLE_DJANGO_TOOLBAR.

Alternatively, you can launch the server using::

    $ ENABLE_DJANGO_TOOLBAR=1 ./manage.py runserver

Requirements
------------

``requirements/production.txt`` will install the requirements needed for production. The requirements used for local development can be found in ``requirements/local.txt``. This requirements file assumes a local checkout of the django-oscar and django-oscar-extensions repos in a folder called ``depends`` adjacent to the checkout of this repo.

The assumption is that when developing on the ecommerce application, you may need to make changes to these other two closely-related projects.

Documentation
-------------

TODO: Link ReadTheDocs

License
-------

The code in this repository is licensed under the AGPL unless
otherwise noted.

Please see ``LICENSE.txt`` for details.

How To Contribute
-----------------

Contributions are very welcome!

Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details.

Even though it was written with ``edx-platform`` in mind, these guidelines
should be followed for Open edX code in general.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Mailing List and IRC Channel
----------------------------

You can discuss this code on the `edx-code Google Group`__ or in the
``#edx-code`` IRC channel on Freenode.

__ https://groups.google.com/forum/#!forum/edx-code
