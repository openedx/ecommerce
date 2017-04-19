Site Command Organization Argument
==================================

This page is about the new argument in ``create_or_update_site`` command (for more details visit `read the docs`_), which
will be used to restrict the admin from adding courses for organizations which are not allowed.

------------------------------
What is organization argument?
------------------------------
If we configure otto for checkout, then against each white label site at edx-platform we have a site in otto for payments.
For example, if we have ``foo.edx.org`` for edx-platform, then we will have ``payments-foo.edx.org`` in otto. Now while
adding new courses as admin at URL ``payments-foo.edx.org/courses``, you want to be sure that courses you are adding must
be from ``foo`` organization, and you cannot submit course from ``bar`` organization.

.. note:: This is an optional argument.

-----------------------------
How to specify this argument?
-----------------------------
Add ``--partner-orgs`` in create or update command, (Orignal command can be viewed on `read the docs`_). And then specify your organization. You can specify multiple organizations also.

+-------------------------+-------------------------------------------------------------------------------------+
| Option                  |    Description                                                                      |
+=========================+=====================================================================================+
| --partner-org=foo       | column spanning                                                                     |
+-------------------------+-------------------------------------------------------------------------------------+
| --partner-org=foo,bar   | To set ``foo`` and ``bar`` as organizations for site                                |
+-------------------------+-------------------------------------------------------------------------------------+
| --partner-org=''        | To unset organizations                                                              |
+-------------------------+-------------------------------------------------------------------------------------+

.. _read the docs: http://edx.readthedocs.io/projects/edx-installing-configuring-and-running/en/latest/ecommerce/install_ecommerce.html#add-another-site-partner-and-site-configuration
