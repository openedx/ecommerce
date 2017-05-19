edX E-Commerce Service  |Travis|_ |Codecov|_
============================================
.. |Travis| image:: https://travis-ci.org/edx/ecommerce.svg?branch=master
.. _Travis: https://travis-ci.org/edx/ecommerce

.. |Codecov| image:: http://codecov.io/github/edx/ecommerce/coverage.svg?branch=master
.. _Codecov: http://codecov.io/github/edx/ecommerce?branch=master

This repository contains the edX E-Commerce Service, which relies heavily on `django-oscar <https://django-oscar.readthedocs.org/en/latest/>`_, as well as all frontend and backend code used to manage edX's product catalog and handle orders for those products.

Prerequisites
-------------
* Python 2.7.x (not tested with Python 3.x)
* `gettext <http://www.gnu.org/software/gettext/>`_
* `npm <https://www.npmjs.org/>`_

Documentation |ReadtheDocs|_
----------------------------
.. |ReadtheDocs| image:: https://readthedocs.org/projects/edx/badge/?version=latest
.. _ReadtheDocs: http://open-edx-ecommerce-guide.readthedocs.io/en/latest/

`Documentation <http://open-edx-ecommerce-guide.readthedocs.io/en/latest/>`_ is hosted on Read the Docs. The source is hosted in this repo's `docs <https://github.com/edx/ecommerce/tree/master/docs>`_ directory. To contribute, please open a PR against this repo.

License
-------

The code in this repository is licensed under the AGPL unless otherwise noted. Please see ``LICENSE.txt`` for details.

How To Contribute
-----------------

Contributions are welcome. Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details. Even though it was written with ``edx-platform`` in mind, these guidelines should be followed for Open edX code in general.

E-Commerce Team SLA
-------------------

Pull Requests made by teams internal to edX will be reviewed within certain timeframes based on the size/complexity of the PR.

+-------------+---------------+----------------+--------------------------+
|             | Lines of Code | Files Modified | SLA                      |
+=============+===============+================+==========================+
| SMALL       | < 10          | 1 - 2          | 2 Days                   |
+-------------+---------------+----------------+--------------------------+
| MEDIUM      | < 300         | 2 - 10         | 7 Days                   |
+-------------+---------------+----------------+--------------------------+
| LARGE       | > 300         | > 10           | 14 Days                  |
+-------------+---------------+----------------+--------------------------+
| EXTRA LARGE | >1000         | > 100          | Team recommends breaking |
|             |               |                | PRs of this size into    |
|             |               |                | smaller chunks of work.  |
+-------------+---------------+----------------+--------------------------+

If the PR is time sensitive, the contributor is encouraged to notify the team well in advance of the need for code review so that the team can plan for the work involved.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Mailing List and Slack
----------------------

You can discuss this code on the `edx-code Google Group <https://groups.google.com/forum/#!forum/edx-code>`_ or on  `Open edX <https://openedx.slack.com/messages/general/>`_  on Slack.
