Acceptance Testing
------------------

In order to run the acceptance tests, complete all of the steps outlined
below, then run the following command:

::

    APP_SERVER_URL="http://localhost:8002" LMS_URL="http://127.0.0.1:8000" LMS_USERNAME="<LMS-USERNAME>" LMS_EMAIL="<LMS-EMAIL>" LMS_PASSWORD="<LMS-PASSWORD>" ACCESS_TOKEN="<ACCESS-TOKEN>" HTTPS_RECEIPT_PAGE=False ENABLE_LMS_AUTO_AUTH=True PAYPAL_EMAIL="<PAYPAL-EMAIL>" PAYPAL_PASSWORD="<PAYPAL-PASSWORD>" VERIFIED_COURSE_ID="<VERIFIED-COURSE-ID>" make accept

In order to run an individual test, simply replace ``make accept`` with
``nosetests -v path/to/the/test/file``. For an explanation of what each
of these environment variables mean, see "Running in a Production
Environment".

Learning Management System (LMS) Settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. In order to begin testing user authentication and course enrollment,
   modify the settings of the LMS server to reflect these changes:

   ::

       ENABLE_OAUTH2_PROVIDER: True,
       OAUTH_ENFORCE_SECURE: False,
       OAUTH_ENFORCE_CLIENT_SECURE: False,
       OAUTH_OIDC_ISSUER: "http://127.0.0.1:8000/oauth2"

   The E-Commerce API URL is often in the following form:
   ``http://{IP Address of VirtualBox}:8002/api/v2``.

2. Next, a Django superuser account must be created if one does not
   currently exist. This can be done by assigning superuser privileges
   to a new edX account. Once a new account has been created, the user
   can be granted superuser status by following the steps below:

   1. Open the Django shell on the LMS server:

      ``./manage.py lms shell --settings=devstack``

   2. In the Django shell, run the following commands:

      ::

          >>> from django.contrib.auth.models import User
          >>> u=User.objects.get(email='{email of new user}')
          >>> u.is_staff = True
          >>> u.is_superuser = True
          >>> u.save()

   3. Exit the Python shell by calling ``exit()``.

3. Once superuser status is in place, navigate to the Django admin panel
   and log in with the new credentials. From here, add a new client with
   the following properties:

   ::

       User: {ID of superuser}
       Url:  http://localhost:8002/
       Redirect url: http://localhost:8002/complete/edx-oidc/
       Client type: Confidential

   Click *Save*.

4. Add this client as a trusted client by clicking on the *Add* button
   next to "Trusted Clients".

5. Add an access token for the superuser by clicking the *Add* button
   next to "Access Tokens". Set the "Client" of the access token to the
   client just created, and make sure that the expiration date is sometime
   into the future.  Make note of this access token, as it will be
   required to run the acceptance tests. Once this step is completed,
   close out of the admin panel.

6. After these settings are confirmed, open
   ``ecommerce/settings/local.py``. Ensure that
   ``SOCIAL_AUTH_EDX_OIDC_KEY`` is set to the client ID of the superuser
   client and that ``SOCIAL_AUTH_EDX_OIDC_SECRET`` is set to the
   superuser's client secret (both of these values can be found in the
   Django admin panel under "Clients"). ``EDX_API_KEY`` should match the
   corresponding value specified on the LMS server.

Oscar E-Commerce Settings
^^^^^^^^^^^^^^^^^^^^^^^^^

1. To ensure Oscar functions correctly with Paypal and Cybersource,
   developer accounts on both sites are required. Once the accounts are
   setup, update the ``PAYMENT_PROCESSOR_CONFIG`` setting in
   ``local.py``.

2. Create a new course in edX Studio and record the course key, which will
   be used later.

3. Navigate back to the LMS Django admin site. Select "Course Modes"
   and click "Add course mode". Add two course modes with the following attributes:

   +--------------------+-----------------------------------+---------------------------------+
   | Attribute          | First Course Mode                 | Second Course Mode              |
   +====================+===================================+=================================+
   | Course id          | {*the course key from earlier*}   | {*the course key from earlier*} |
   +--------------------+-----------------------------------+---------------------------------+
   | Mode slug          | honor                             | verified                        |
   +--------------------+-----------------------------------+---------------------------------+
   | Mode display name  | Honor                             | Verified                        |
   +--------------------+-----------------------------------+---------------------------------+
   | Min price          | 0                                 | {*any # greater than 0*}        |
   +--------------------+-----------------------------------+---------------------------------+
   | SKU                | honor-variant                     | verified-variant                |
   +--------------------+-----------------------------------+---------------------------------+

4. Login to the Oscar dashboard as the superuser.

5. Create a new product:

   1. From the menu, select Products > Catalogue.
   2. Add a new product of type "Seat" and fill it out with the new
      course information.
   3. Under the "Categories" tab, set the category to type "Seat".
   4. Under the "Attributes" tab, set the course key to the course key
      of the new course.
   5. Set the certificate type to type "verified".

6. Under the "Variants" tab, add two course variants, each with the
   following settings:

   +--------------------+-----------------------------------+-----------------------------------+
   | Attribute          | First Variant                     | Second Variant                    |
   +====================+===================================+===================================+
   | Name               | Honor                             | Verified                          |
   +--------------------+-----------------------------------+-----------------------------------+
   | Certificate Type   | honor                             | verified                          |
   +--------------------+-----------------------------------+-----------------------------------+
   | Course Key         | (*the course key from earlier*)   | (*the course key from earlier*)   |
   +--------------------+-----------------------------------+-----------------------------------+
   | Partner            | edX                               | edX                               |
   +--------------------+-----------------------------------+-----------------------------------+
   | Price (excl tax)   | 0                                 | (*any # greater than 0*)          |
   +--------------------+-----------------------------------+-----------------------------------+
   | SKU                | honor-variant                     | verified-variant                  |
   +--------------------+-----------------------------------+-----------------------------------+

   Be sure that the currency between the variants and the course modes match before continuing.

Running in a Production Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the acceptance tests are to be run in a production environment, the
below table should be used to determine the appropriate environment
variables that should be set.

+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| Variable                  | Purpose                                                                  | Example                                   |
+===========================+==========================================================================+===========================================+
| BASIC\_AUTH\_USERNAME     | Username for basic server authentication                                 | MyUsername                                |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| BASIC\_AUTH\_PASSWORD     | Password for basic server authentication                                 | my\_pass1234                              |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| APP\_SERVER\_URL          | The URL of the E-Commerce server                                         | https://ecommerce.example.com             |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| LMS\_URL                  | URL of the LMS server                                                    | https://courses.example.com               |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| LMS\_USERNAME             | Username of the LMS user account                                         | MyUsername                                |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| LMS\_EMAIL                | Email of the LMS user account                                            | MyEmail@example.com                       |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| LMS\_PASSWORD             | Password of the LMS user account                                         | my\_pass1234                              |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| ACCESS\_TOKEN             | Access token for the LMS user account                                    | abcd1234                                  |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| HTTPS\_RECEIPT\_PAGE      | Indicates whether the receipt page uses SSL                              | True                                      |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| ENABLE\_LMS\_AUTO\_AUTH   | | Indicates whether auto auth should be used when testing registration   | False                                     |
|                           | | If auto auth is used, LMS credentials can be omitted.                  |                                           |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| PAYPAL\_EMAIL             | Email address for the PayPal account to use                              | testUser-buyer@example.com                |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| PAYPAL\_PASSWORD          | Password for the PayPal account to use                                   | test\_pass1234                            |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
| VERIFIED\_COURSE\_ID      | Course ID of a verified course                                           | edx/verified-course/verified\_course\_1   |
+---------------------------+--------------------------------------------------------------------------+-------------------------------------------+
