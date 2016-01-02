Getting Started
===============

If you have not already done so, create/activate a `virtualenv`_. Unless otherwise stated, assume all terminal code
below is executed within the virtualenv.

.. _virtualenv: https://virtualenvwrapper.readthedocs.org/en/latest/


Install dependencies
--------------------
Dependencies can be installed via the command below.

.. code-block:: bash

    $ make requirements


Local/Private Settings
----------------------
When developing locally, it may be useful to have settings overrides that you do not wish to commit to the repository.
If you need such overrides, create a file :file:`ecommerce/settings/private.py`. This file's values are
read by :file:`ecommerce/settings/local.py`, but ignored by Git.


Configure edX OpenID Connect (OIDC)
-----------------------------------
This service relies on the edX OIDC (`OpenID Connect`_) authentication provider for login. Note that OIDC is built atop
OAuth 2.0, and this document may use the terms interchangeably. Under our current architecture the LMS serves as our
authentication provider.

Configuring E-Commerce Service to work with OIDC requires registering a new client with the authentication
provider and updating the Django settings for this project with the client credentials.

.. _OpenID Connect: http://openid.net/specs/openid-connect-core-1_0.html


A new OAuth 2.0 client can be created at ``http://127.0.0.1:8000/admin/oauth2/client/``.

    1. Click the :guilabel:`Add client` button.
    2. Leave the user field blank.
    3. Specify the name of this service, ``E-Commerce Service``, as the client name.
    4. Set the :guilabel:`URL` to the root path of this service: ``http://localhost:8002/``.
    5. Set the :guilabel:`Redirect URL` to the OIDC client endpoint: ``https://localhost:8002/complete/edx-oidc/``.
    6. Copy the :guilabel:`Client ID` and :guilabel:`Client Secret` values. They will be used later.
    7. Select :guilabel:`Confidential (Web applications)` as the client type.
    8. Click :guilabel:`Save`.

Your newly-created client must also be designated as trusted. Trusted clients bypass the user consent form typically displayed after validating the user's credentials. Create a new trusted client at ``http://127.0.0.1:8000/admin/oauth2_provider/trustedclient/add/``.

    1. Select your newly-created client's redirect URL from the dropdown.
    2. Click ``Save``.

Now that you have the client credentials, you can update your settings (ideally in
:file:`ecommerce/settings/local.py`). The table below describes the relevant settings.

+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| Setting                                             | Description                                                                | Value                                                                    |
+=====================================================+============================================================================+==========================================================================+
| SOCIAL_AUTH_EDX_OIDC_KEY                            | OAuth 2.0 client key                                                       | (This should be set to the value generated when the client was created.) |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| SOCIAL_AUTH_EDX_OIDC_SECRET                         | OAuth 2.0 client secret                                                    | (This should be set to the value generated when the client was created.) |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| SOCIAL_AUTH_EDX_OIDC_URL_ROOT                       | OAuth 2.0 authentication URL                                               | http://127.0.0.1:8000/oauth2                                             |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY        | OIDC ID token decryption key. This value is used to validate the ID token. | (This should be the same value as SOCIAL_AUTH_EDX_OIDC_SECRET.)          |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+


Run migrations
--------------
Local installations use SQLite by default. If you choose to use another database backend, make sure you have updated
your settings and created the database (if necessary). Migrations can be run with `Django's migrate command`_.

.. code-block:: bash

    $ make migrate

.. _Django's migrate command: https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-migrate


Run the server
--------------
The server can be run with `Django's runserver command`_. If you opt to run on a different port, make sure you update
OIDC client via LMS admin.

.. code-block:: bash

    $ python manage.py runserver 8002

If you're running on devstack, you'll need to pass the appropriate settings:

.. code-block:: bash

    $ python manage.py runserver 0.0.0.0:8002 --settings=ecommerce.settings.devstack

.. _Django's runserver command: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port


Create a course mode with the course admin tool
-----------------------------------------------
If you're using `devstack`_, the ecommerce and edx-platform servers
already have the correct configuration defaults to communicate with
one another. To configure course modes for a course, do the following:

1. On `devstack`_, bring up the ecommerce server on port 8002, and the LMS on port 8000.
2. On the ecommerce server, set up a `SiteConfiguration`_ in the django admin.
3. Head over to the courses page on the ecommerce server: http://localhost:8002/courses.
4. Click "Add New Course".

From there, you should be able to enter in the course id and desired course mode
for the course you'd like to configure.

.. _SiteConfiguration: http://open-edx-ecommerce-guide.readthedocs.org/en/latest/partner_config.html#site-configuration-model-django-admin



Development outside devstack
----------------------------
If you are using `devstack`_ for platform development, you may still wish to install and run this service on your host
operating system.  One simple way to achieve this is setting up a reverse port-forward, such as the following:

.. code-block:: bash

    $ vagrant ssh -- -R 8002:127.0.0.1:8002  # run on the vm host, not the guest.

This will allow your LMS process inside devstack to make calls to your ecommerce server running on the host, via
'127.0.0.1:8002', simplifying URL configuration in the LMS.

.. _devstack: https://github.com/edx/configuration/wiki/edX-Developer-Stack
