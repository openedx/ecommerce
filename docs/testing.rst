Testing
=======

To run the unit test suite followed by quality checks, run:

.. code-block:: bash

    $ make validate

The unit tests run database migrations by default. These migrations can take up to two minutes to run. Most local development
won't require migrations. You can save time by disabling migrations when running tests locally with the command below:

.. code-block:: bash

    $ DISABLE_MIGRATIONS=1 make validate

Code quality validation can be performed independently with:

.. code-block:: bash

    $ make quality

Writing Tests
-------------
Tests should be written for all new features. The `Django docs`_ are a good resource to learn how to test Django code.
When creating tests, use the ``TestCase`` class in ``ecommerce/tests/testcases.py`` to ensure every test has ``Site`` and
``Partner`` objects configured. This will aid testing any code that might rely on these models (which are used for
multi-tenancy).

.. _Django docs: https://docs.djangoproject.com/en/1.8/topics/testing/

This project uses `Jasmine <http://jasmine.github.io/2.3/introduction.html>`_ for JavaScript unit testing.
Tests should be placed in ``ecommerce/static/js/test/specs`` and suffixed with ``_spec``.
For example, ``ecommerce/static/js/test/specs/course_list_view_spec.js``. All JavaScript code should adhere to the
`edX JavaScript standards <https://github.com/edx/edx-platform/wiki/Javascript-standards-for-the-edx-platform>`_.
These standards are enforced using `JSHint <http://www.jshint.com/>`_ and `jscs <https://www.npmjs.org/package/jscs>`_.



Acceptance Testing
------------------

The project also includes acceptance tests used to verify behavior which relies on external systems like the LMS
and payment processors. At a minimum, these tests should be run against a staging environment before deploying
code to production to verify that critical user workflows are functioning as expected. With the right configuration
in place, the tests can also be run locally. Below you'll find an explanation of how to configure the LMS and the
E-Commerce Service so that the acceptance tests can be run successfully.

Definitions
***********

Definitions of commonly used terms:

* LMS: The edX Learning Management System. Course content is found here.
* Otto: Nickname used to refer to the edX E-Commerce Service, a Django application used to manage edX's product catalog and handle orders for those products.
* CAT: The Course Administration Tool, part of Otto. Provides a UI which can be used to configure and otherwise manage products associated with courses available on the LMS.

LMS Configuration
*****************

Running the acceptance tests successfully requires that you first correctly configure the LMS and Otto. We'll start with the LMS.

#. Verify that the following settings in ``lms.env.json`` are correct::

    "ECOMMERCE_API_URL": "http://localhost:8002/api/v2/"
    "ECOMMERCE_PUBLIC_URL_ROOT": "http://localhost:8002/"
    "JWT_ISSUER": "http://127.0.0.1:8000/oauth2" // Must match Otto's JWT_ISSUER setting
    "OAUTH_ENFORCE_SECURE": false
    "OAUTH_OIDC_ISSUER": "http://127.0.0.1:8000/oauth2"

#. Verify that the following settings in ``lms.auth.json`` are correct::

    "EDX_API_KEY": "replace-me" // Must match Otto's EDX_API_KEY setting
    "ECOMMERCE_API_SIGNING_KEY": "insecure-secret-key" // Must match Otto's JWT_SECRET_KEY setting

#. To faciliate the following configuration steps, verify that an LMS account with staff and superuser permissions exists. On most LMS instances, a user with the username ``staff``, the email address ``staff@example.com``, and the password ``edx`` will already have staff permissions. Grant the account superuser privileges as follows::

    $ ``./manage.py lms shell --settings=devstack``
    >>> from django.contrib.auth.models import User
    >>> u = User.objects.get(username='staff')
    >>> u.is_superuser = True
    >>> u.save()

#. Navigate to the Django admin and verify that an OAuth2 client with the following attributes exists. If one doesn't already exist, create a new one. The client ID and secret must match the values of Otto's ``SOCIAL_AUTH_EDX_OIDC_KEY`` and ``SOCIAL_AUTH_EDX_OIDC_SECRET`` settings, respectively. ::

    URL:  http://localhost:8002/
    Redirect URI: http://localhost:8002/complete/edx-oidc/
    Client ID: 'replace-me'
    Client Secret: 'replace-me'
    Client Type: Confidential

#. In the Django admin, verify that the OAuth2 client referred to above is designated as a trusted client. If this isn't already the case, add the client created above as a new trusted client.

#. In the Django admin, create a new access token for the superuser referred to previously. Set the client to the OAuth2 client referred to above. Make note of this token; it is required to run the acceptance tests.

#. At a minimum, the acceptance tests require the existence of two courses on the LMS instance being used for testing. The edX Demonstration Course should be present by default on most LMS instances. Use Studio to create a second course now.

Otto Configuration
******************

#. Use the CAT to finish configuring the courses you created above. You can find the CAT at ``http://localhost:8002/courses/``. Add both of the courses present on your LMS instance to Otto. Configure one as "Free (Honor)" course, and the second as a "Verified" course.

#. Testing integration with external payment processors requires updating the contents of the ``PAYMENT_PROCESSOR_CONFIG`` dictionary found in the settings with valid credentials. To override the default values for development, create a private settings module, ``private.py``, and add set ``PAYMENT_PROCESSOR_CONFIG`` within.

Environment Variables
*********************

Our acceptance tests rely on configuration which can be specified using environment variables.

+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| Variable                  | Purpose                                                                  | Required? | Default Value                        |
+===========================+==========================================================================+===========+======================================+
| ACCESS\_TOKEN             | OAuth2 access token used to authenticate requests                        | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ENABLE\_OAUTH2\_TESTS     | Whether to run tests verifying that the LMS can be used to sign into Otto| No        | True                                 |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| HONOR\_COURSE\_ID         | The ID of a Free (Honor) course                                          | No        | 'edX/DemoX/Demo_Course'              |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| VERIFIED\_COURSE\_ID      | The ID of a Verified course                                              | No        | 'edX/victor101/Victor_s_test_course' |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ECOMMERCE\_URL\_ROOT      | URL root for the E-Commerce Service                                      | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ECOMMERCE\_API\_URL       | URL for the E-Commerce API, used to initialize an API client             | No        | ECOMMERCE\_URL\_ROOT + '/api/v2'     |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ECOMMERCE\_API\_TOKEN     | Token used to authenticate against the E-Commerce API                    | No        | ACCESS\_TOKEN                        |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| MAX\_COMPLETION\_RETRIES  | Number of times to retry checking for an order's completion              | No        | 3                                    |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| PAYPAL\_EMAIL             | Email address used to sign into PayPal during payment                    | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| PAYPAL\_PASSWORD          | Password used to sign into PayPal during payment                         | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ENABLE\_CYBERSOURCE\_TESTS| Whether to run tests verifying the CyberSource payment flow              | No        | True                                 |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| LMS\_URL\_ROOT            | URL root for the LMS                                                     | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| LMS\_USERNAME             | Username belonging to an LMS user to use during testing                  | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| LMS\_EMAIL                | Email address used to sign into the LMS                                  | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| LMS\_PASSWORD             | Password used to sign into the LMS                                       | Yes       | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| LMS\_AUTO\_AUTH           | Whether auto-auth is enabled on the LMS                                  | No        | False                                |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| LMS\_HTTPS                | Whether HTTPS is enabled on the LMS                                      | No        | True                                 |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ENROLLMENT\_API\_URL      | URL for the LMS Enrollment API                                           | No        | LMS\_URL\_ROOT + '/api/enrollment/v1'|
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| ENROLLMENT\_API\_TOKEN    | Token used to authenticate against the Enrollment API                    | No        | ACCESS\_TOKEN                        |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| BASIC\_AUTH\_USERNAME     | Username used to bypass HTTP basic auth on the LMS                       | No        | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+
| BASIC\_AUTH\_PASSWORD     | Password used to bypass HTTP basic auth on the LMS                       | No        | N/A                                  |
+---------------------------+--------------------------------------------------------------------------+-----------+--------------------------------------+

Running Acceptance Tests
************************

Run all acceptance tests by executing ``make accept``. To run a specific test, execute::

    $ nosetests -v <path/to/the/test/module>

As discussed above, the acceptance tests rely on configuration which can be specified using environment variables. For example, when running the acceptance tests against local instances of Otto and the LMS, you might run::

    $ ECOMMERCE_URL_ROOT="http://localhost:8002" LMS_URL_ROOT="http://127.0.0.1:8000" LMS_USERNAME="<username>" LMS_EMAIL="<email address>" LMS_PASSWORD="<password>" ACCESS_TOKEN="<access token>" LMS_HTTPS="False" LMS_AUTO_AUTH="True" PAYPAL_EMAIL="<email address>" PAYPAL_PASSWORD="<password>" ENABLE_CYBERSOURCE_TESTS="False" VERIFIED_COURSE_ID="<course ID>" make accept

When running against a production-like staging environment, you might run::

    $ ECOMMERCE_URL_ROOT="https://ecommerce.stage.edx.org" LMS_URL_ROOT="https://courses.stage.edx.org" LMS_USERNAME="<username>" LMS_EMAIL="<email address>" LMS_PASSWORD="<password>" ACCESS_TOKEN="<access token>" LMS_HTTPS="True" LMS_AUTO_AUTH="False" PAYPAL_EMAIL="<email address>" PAYPAL_PASSWORD="<password>" BASIC_AUTH_USERNAME="<username>" BASIC_AUTH_PASSWORD="<password>" HONOR_COURSE_ID="<course ID>" VERIFIED_COURSE_ID="<course ID>" make accept


