======================
Order Fulfillment
======================

Since ``django-oscar`` doesn't offer a lot of specific functionality in this area, we have put together our own framework for handling fulfillment. Since all of our current products are digital, we need to be able to be able to correctly fulfill these orders in code.

---------------------
Fulfillment API
---------------------

In order to address this, we will be hooking into ``order.processing.EventHandler#handler_shipping_event()``, which will make calls to ``fulfillment_api.fulfill(order)``.

The Fulfillment API will then be responsible for delegating fulfillment of the individual order items to the appropriate Fulfillment Modules.


---------------------
Fulfillment Modules
---------------------

There will be a base fulfillment module that has the following interface::
    
    fulfill_product(product)

    revoke_product(product)


For each ``ProductType`` that we develop, there will be a corresponding module that will extend this interface and be responsible for fulfilling order items of that particular ``ProductType``. The mapping between each ``ProductType`` and the corresponding fulfillment module will be configured in ``settings.py`` as a simple dictionary.

``fulfill_product`` will fulfill the given product (i.e., enroll a student in a course, upgrade the student to a verified certificate).

``revoke_product`` will do the opposite (i.e., unenroll students from courses, downgrade people from veriied).

Both of these methods will return a JSON-serializable dictionary containing both the status and any important status notes.

For example, a success would return something like ``{'status': 'success'}`` and a failure would return something like ``{'status': 'failure', 'error_type': 'Connection Refused'}``.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Enrollment Fulfillment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Most of the products that edX supports involve modifications to enrollments.

The modules that are responsible for fulfillment of enrollment-related products will interface with the `LMS-provided Enrollment API <http://edx-enrollment-api.readthedocs.org/>`_. This process will be synchronous.

------------------------------
Error Recovery in Fulfillment
------------------------------

For a variety of reasons, fulfillment of a product may fail. In order to handle these situations, we will record a status after payment has been received and before the order has been fulfilled. We can create a new ``Order Status`` via ``order.abstract_models.AbstractOrder`` to track this failed fulfillment attempt. A celery task -- or some other sort of queueing mechanism -- will be responsible for re-attempting to fulfill orders that failed to be fulfilled the first time around.
