.. _Install and Start ECommerce:

########################################
Install and Start the E-Commerce Service
########################################

.. warning::
 This document is out of date regarding virtual environment configuration.
 E-Commerce should be properly provisioned for you as part of Dockerized `devstack`_.

To install and start the edX E-Commerce service, you must complete the
following steps.

.. contents::
   :depth: 1
   :local:

.. note::
 These steps assume that you are running Open edX `devstack`_. If you prefer to
 run the E-Commerce service locally on your computer instead of on the virtual
 machine (VM) that devstack uses, see :`Development Outside Devstack`_.

****************************
Set Up a Virtual Environment
****************************

#. Create or activate a Python virtual environment. You execute all of the
   commands described in this section within the virtualenv (unless otherwise
   noted).

   For more information, see `Virtual Environments`_.

#. Run the following command to install dependencies.

   .. code-block:: bash

    $ make requirements

#. (Optional) Create settings overrides that you do not commit to the
   repository. To do this, create a file named
   ``ecommerce/settings/private.py``. The ``ecommerce/settings/local.py`` file
   reads the values in this file, but Git ignores the file.

.. _Run Migrations:

**************
Run Migrations
**************

To set up the ``ecommerce`` database, you must run migrations.

.. note::
    Local installations use SQLite by default. If you use another database
    backend, make sure you update your settings and create the database, if
    necessary, before you run migrations.

#. To run migrations, execute the following command.

   .. code-block:: bash

      $ make migrate

When you run migrations, the E-Commerce service adds a default site to your installation.

***************
Configure OAuth
***************

The E-Commerce service relies on the LMS, which serves as the OAuth 2.0 authentication provider.

To configure the E-Commerce service to work with OAuth, complete the following
procedures.

.. contents::
   :depth: 1
   :local:

============================
Create and Register a Client
============================

To create and register a new OAuth client, follow these steps.

#. Start the LMS.
#. In your browser, go to ``http://127.0.0.1:8000/admin/oauth2_provider/application/``.
#. Select **Add client**.
#. Leave the **User** field blank.
#. For **Client Name**, enter ``E-Commerce Service``.
#. For **URL**, enter ``http://localhost:8002/``.
#. For **Redirect URL**, enter ``http://127.0.0.1:8002/complete/edx-oauth2/``.
   This is the OAuth client endpoint.

   The system automatically generates values in the **Client ID** and **Client
   Secret** fields.

#. For **Client Type**, select **Authorization code**.
#. Enable **Skip authorization**.
#. Select **Save**.

.. _Configure a Site Partner and Site Configuration:

*************************************************
Configure a Site, Partner, and Site Configuration
*************************************************

To finish creating and configuring your OAuth client, you must configure a
partner, site, and site configuration for the E-Commerce service to use. The
site that you configure is the default site that the E-Commerce service adds
when you run migrations. You must update this default site to match the domain
that you will use to access the E-Commerce service. You must also set up a site
configuration that contains an ``oauth_settings`` JSON field that stores your
OAuth client's settings, as follows.

.. list-table::
   :widths: 25 60 20
   :header-rows: 1

   * - Setting
     - Description
     - Value
   * - ``BACKEND_SERVICE_EDX_OAUTH2_KEY``
     - OAuth 2.0 client key
     - The **Client ID** field in the `Create and Register a Client`_
       section for backend server-to-server calls.
   * - ``BACKEND_SERVICE_EDX_OAUTH2_SECRET``
     - OAuth 2.0 client secret
     - The **Client Secret** field in the `Create and Register a Client`_
       ection for backend server-to-server calls.
   * - ``SOCIAL_AUTH_EDX_OAUTH2_KEY``
     - OAuth 2.0 client key
     - The **Client ID** field in the `Create and Register a Client`_ section.
   * - ``SOCIAL_AUTH_EDX_OAUTH2_SECRET``
     - OAuth 2.0 client secret
     - The **Client Secret** field in the `Create and Register a Client`_ section.
   * - ``SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT``
     - OAuth 2.0 authentication URL
     - For example, ``http://127.0.0.1:8000``.
   * - ``SOCIAL_AUTH_EDX_OAUTH2_ISSUER``
     - OAuth token issuer
     - For example, ``http://127.0.0.1:8000``.
   * - ``SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL``
     - User logout URL
     - For example, ``http://127.0.0.1:8000/logout``.

To configure your default site, partner, and site configuration, use the
appropriate settings module for your environment
(``ecommerce.settings.devstack`` for Devstack,
``ecommerce.settings.production`` for Fullstack) to run the following Django
management command. This command updates the default site and creates a new
partner and site configuration with the specified options.

    .. code-block:: bash

      $ sudo su ecommerce
      $ python manage.py create_or_update_site --site-id=1 --site-domain=localhost:8002 --partner-code=edX --partner-name='Open edX' --lms-url-root=localhost:8000 --theme-scss-path=sass/themes/edx.scss --payment-processors=cybersource,paypal --backend-service-client-id=[Change to OAuth Client ID for backend service calls] --backend-service-client-key=[Change to OAuth Client Secret for backend service calls] --sso-client-id=[Change to OAuth Client ID for SSO calls] --sso-client-key=[Change to OAuth Client Secret for SSO calls]

.. _Add Another Site Partner and Site Configuration:

=================================================
Add Another Site, Partner, and Site Configuration
=================================================

If you want to add more sites, partners, and site configurations, you can use
the ``create_or_update_site`` command. The following options are available for
this command.

.. list-table::
   :widths: 25 20 60 20
   :header-rows: 1

   * - Option
     - Required
     - Description
     - Example
   * - ``--site-id``
     - No
     - Database ID of a site you want to update.
     - ``--site-id=1``
   * - ``--site-domain``
     - Yes
     - Domain by which you will access
       the E-Commerce service.
     - ``--site-domain=ecommerce.example.com``
   * - ``--site-name``
     - No
     - Name of the E-Commerce site.
     - ``--site-name='Example E-Commerce'``
   * - ``--partner-code``
     - Yes
     - Short code of the partner.
     - ``--partner-code=edX``
   * - ``--partner-name``
     - No
     - Name of the partner.
     - ``--partner-name='Open edX'``
   * - ``--lms-url-root``
     - Yes
     - URL root of the Open edX LMS instance.
     - ``--lms-url-root=https://example.com``
   * - ``--theme-scss-path``
     - No
     - ``STATIC_ROOT`` relative path of the site's SCSS file.
     - ``--theme-scss-path=sass/themes/edx.scss``
   * - ``--payment-processors``
     - No
     - Comma-delimited list of payment processors used on the site.
     - ``--payment-processors=cybersource,paypal``
   * - ``--client-id``
     - Yes
     - OAuth client ID.
     - ``--client-id=ecommerce-key``
   * - ``--client-secret``
     - Yes
     - OAuth client secret.
     - ``--client-secret=ecommerce-secret``
   * - ``--from-email``
     - Yes
     - Address from which email messages are sent.
     - ``--from-email=notifications@example.com``
   * - ``--enable-enrollment-codes``
     - No
     - Indication that specifies whether enrollment codes for seats can be
       created.
     - ``--enable-enrollment-codes=True``
   * - ``--payment-support-email``
     - No
     - Email address displayed to user for payment support.
     - ``--payment-support-email=support@example.com``
   * - ``--payment-support-url``
     - No
     - URL displayed to user for payment support.
     - ``--payment-support-url=https://example.com/support``


To add another site, use the appropriate settings module for your environment
(``ecommerce.settings.devstack`` for Devstack,
``ecommerce.settings.production`` for Fullstack) to run the following Django
management command. This command creates a new site, partner, and site
configuration with the options that you specify.

    .. code-block:: bash

      $ sudo su ecommerce
      $ python manage.py create_or_update_site --site-domain=[change me] --partner-code=[change me] --partner-name=[change me] --lms-url-root=[change me] --client-id=[OAuth client ID] --client-secret=[OAuth client secret] --from-email=[from email]

****************
Start the Server
****************

To complete the installation and start the E-Commerce service, follow these
steps.

.. note::
    Local installations use SQLite by default. If you use another database
    backend, make sure you update your settings and create the database, if
    necessary, before you run migrations.

#. (Devstack only) If you are using devstack, switch to the ``ecommerce`` user
   and use the ``ecommerce.settings.devstack`` settings module to run the
   following commands.

    .. code-block:: bash

      $ sudo su ecommerce
      $ make serve

#. To run the server, execute the following command.

   .. code-block:: bash

     $ python manage.py runserver 8002

   .. note::
     If you use a different port, make sure you update the OAuth client by using
     the Django administration panel in the LMS. For more information about
     configuring the OAuth client, see `Configure OAuth`_.

*****************************************
Switch from ShoppingCart to E-Commerce
*****************************************

By default, the ShoppingCart service is enabled when you install an Open edX
instance. To use the E-Commerce service to handle ecommerce-related tasks
instead of ShoppingCart, follow these steps.

#. Sign in to the Django administration console for your base URL. For example,
   ``http://{your_URL}/admin``.

#. In the **Commerce** section, next to **Commerce configuration**, select **Add**.

#. Select **Enabled**.

#. Select **Checkout on ecommerce service**.

#. (Optional) In the **Single course checkout page**  field, override the
   default path value of ``/basket/single-item/`` with your own path value.

   .. important:: If you override the default path value, you must also change
     all of the code that relies on that path.

#. Set the **Cache Time To Live** value in seconds.

#. Select the site for which you want to enable the E-Commerce service.

#. Select **Save**.

****************************
Development Outside Devstack
****************************

If you are running the LMS in `devstack`_ but would prefer to run the
E-Commerce service on your host, set up a reverse port-forward. This reverse
port-forward allows the LMS process inside your devstack to use
``127.0.0.1:8002`` to make calls to the E-Commerce service running on your
host. This simplifies LMS URL configuration.

To set up a reverse port-forward, execute the following command when you SSH
into your devstack. Make sure that you run this command on the VM host, not the
guest.

.. code-block:: bash

    $ vagrant ssh -- -R 8002:127.0.0.1:8002




.. include:: links/links.rst
