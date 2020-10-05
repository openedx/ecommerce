5. Payment Microfrontend (MFE) Support and Backend-for-Frontend (BFF) APIs
--------------------------------------------------------------------------

Status
------

Accepted

Context
-------

As part of the re-platforming effort to rewrite our server-side templates as microfrontends (MFEs), the ecommerce basket page was targeted for rewrite.

Detailing the general decision around moving to MFEs is out of scope of this ADR.

Decision
--------

The updated basket page was called the Payment page or Payment MFE.

Backend-for-Frontend (BFF) APIs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A set of backend-for-frontend (BFF) APIs were introduced which are specifically designed for the new Payment MFE. These fall under the category of **Feature-driven APIs** as depicted in `edX REST API Trichotomy`_. Generally, the endpoints follow the best practices as defined by `edX REST API Conventions`_. However, the BFF API endpoints do have some special requirements as detailed below::

* The language used for the BFF endpoints and JSON response keys should match the language used in the frontend, and hide the language of django-oscar and the server. For example, favor the term "coupon" over "voucher".

* The BFF urls follow a format like ``/bff/payment/v1/payment/``, rather than using the ``/api`` naming convention.

    * Although a ``bff`` directory and ``payment`` subdirectory were added to define the urls, the implementation of the API views were co-located with the original basket views.

    * As of 8/20/2019, `ARCH-1073`_ documents the following changes to better match best practices:

        * The endpoints should be updated from ``v0`` to ``v1``.

        * The endpoints currently using ``/voucher`` should be updated to ``/coupon``.

* Each BFF endpoint (e.g. get payment, add coupon (voucher), delete coupon (voucher), etc.) was designed to return the full results of the user's basket.  The endpoints are optimized for the MFE to make fewer calls, rather than requiring the MFE to make one call to update the basket and a separate call to get the updated details of the basket.

* BFF APIs handle redirects by returning a status of 200 with the following format::

    {'redirect': REDIRECT_URL}

* The ecommerce service, built using django-oscar, made use of Django's flash messages for handling server-side generated user messages (e.g. info, error). A set of message utilities were created to read the flash messages and output the messages in the form of JSON.

    * To support the features of flash messages (e.g. message type), the following additions were made to the `edX REST API Conventions`_:

        * A key ``messages`` contains an array of message objects, to allow for multiple messages of different types.

        * The key ``message_type`` allows the frontend to differentiate message types like warning and error.  The simpler key ``type`` interfered with a keyword in JavaScript or one of the libraries.

        * Simple text messages used the ``user_message`` key defined in the conventions and is displayed as-is in the frontend.

        * Server-side messages that included HTML-markup were reimplemented directly in the frontend in order to avoid any potential for XSS, and to let the frontend handle all markup.

            * In these cases, the message would contain a ``code`` that could be looked up in the client.

            * A special ``data`` object could also be included with key/value pairs of message specific data that could be interpolated into the message on the client.  Note that the keys for this data need are part of the contract for a given message code from the server.

    *  See message_utils.py for further detail.

* The new BFF endpoints were implemented sharing as much code as possible with the original server-side templates.

.. _ARCH-1073: https://openedx.atlassian.net/browse/ARCH-1073
.. _message_utils.py: https://github.com/edx/ecommerce/blob/438085a194729fc0843c2791e85d649bc9bdafb4/ecommerce/extensions/basket/message_utils.py

Other API Updates Supporting the Payment MFE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A new view CybersourceSubmitAPIView was created as a DRF wrapper of CybersourceSubmitView, enabling JWT Authentication on the new API view for the microfrontend.

    * Unlike the BFF endpoints this simple wrapper does not use the language of the frontend. The frontend thus translates from the server-side names of the fields to the frontend names.

Additionally, the BasketAddItemsView was converted to a DRF API endpoint using the new ``LoginRedirectIfUnauthenticated`` permission class. This enables ``/basket/add`` calls, which are made before reaching the Payment MFE, to use JWT Authentication and avoid initiating the old ecommerce SSO flow which is slow and unnecessary for the Payment MFE which uses JWT Authentication.

Configuration and URLs
~~~~~~~~~~~~~~~~~~~~~~

Because of pending plans to support independent configuration of MFEs, site-specific configuration on the server is not sent to the Payment MFE. Instead, this configuration is currently duplicated on the MFE and should eventually be deleted from the server. Example configuration settings include URLs for CyberSource and Apple Pay and whether the SDN check is enabled.  See `frontend-app-payment documentation`_ for more details.

Payment Processors
~~~~~~~~~~~~~~~~~~

As of 8/2019, the initial implementation of the Payment MFE no longer allows the payment processors to be pluggable on the frontend. This can be revisited when and if necessary.

Absolute Redirects
~~~~~~~~~~~~~~~~~~

The Payment MFE is currently hosted using a different subdomain than the ecommerce backend service. Payment MFE calls to the ecommerce backend that result in a redirect from the ecommerce service need to use an absolute url, rather than a relative url, in order to avoid redirecting to the Payment MFE when you actually want to redirect to the ecommerce service.

Django's reverse call returns a relative url by default. Instead, you can use the `absolute_redirect method`_ to appropriately redirect to the ecommerce service in these cases.

Consequences
------------

The backend-for-frontend (BFF) endpoints were not designed for general use and thus are unlikely to serve any other
purpose than supporting a Payment microfrontend, falling under the category of `edX's Feature-driven APIs`_.

Refactoring the original server-side views in order to share its code with the new BFF endpoints meant increased risk for introducing bugs into existing views, but reduced risk of having the two implementations drift while they both exist.

References
----------

* `edX REST API Trichotomy`_
* `edX REST API Conventions`_
* `frontend-app-payment documentation`_

.. _edX REST API Conventions: https://openedx.atlassian.net/wiki/spaces/AC/pages/18350757/edX+REST+API+Conventions#edXRESTAPIConventions-5.Errors
.. _edX REST API Trichotomy: https://openedx.atlassian.net/wiki/spaces/AC/pages/790036554/REST+API+Trichotomy+Proposal
.. _edX's Feature-driven APIs: https://openedx.atlassian.net/wiki/spaces/AC/pages/790036554/REST+API+Trichotomy+Proposal
.. _frontend-app-payment documentation: https://github.com/edx/frontend-app-payment/blob/master/README.rst
.. _absolute_redirect method: https://github.com/edx/ecommerce/blob/1b102573c86027a713d216702add61d5c63b8a40/ecommerce/core/url_utils.py#L122-L123
