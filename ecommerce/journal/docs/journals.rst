=====================================
Journal Service Ecommerce Integration
=====================================

The Journal Product enables organizations to provide educational
resources that are better surfaced outside of the course experience. For
more information and to see the source code checkout the `journals repo`_:

This module contains the necessary integrations to make the journals
product purchasable. It is also a rough primer on some important basics
of how edx-ecommerce works.

A New Journal Product Class
===========================

Oscar has a concept *product class* (in the Oscar UI it’s referred to as
*product type*). This is just a type of product, like *course seat* or
*course entitlement*.

Creating a New Product Class
----------------------------

New product classes can be made manually through the oscar dashboard: http://localhost:18130/dashboard/catalogue/product-types/

But we want that product type to exist even if we reprovision ecommerce, and to exist on every environment without manual intervention.  So we manually make a migration: `0031_journal_product_class`_ 

-  This migration writes a new row to the ``catalogue_productclass`` table, creating the product class ``Journal``
-  It also writes a row to the ``catalogue_productattribute`` table, which specifies that the product class ``Journal`` has an attribute ``UUID``

Important tables that define a product in oscar:

-  ``catalogue_productclass``: defines types of products
-  ``catalogue_productattribute``: defines a set of attributes for a given product type

   -  *For example*: the ``Journal`` product class has one product attribute associated with it, that is ``UUID``. Other products may have no or multiple attributes.
   -  Again, this could be done through the oscar UI, but we do this through migrations to make sure that it persists through provisions: http://localhost:18130/dashboard/catalogue/product-type/6/update/#product_attributes

-  ``catalogue_product``: describes an instance of a product

   -  *For example*: You may have the product class ``course seat``, but an instance of that product may be ``seat in course DemoX``
   -  You can create a new product through the dashboard: http://localhost:18130/dashboard/catalogue/
   -  We do not create journals through the oscar dashboard, see `Creating a new instance of a Journal Product`_ below
   -  `catalogue_productattributevalue`: describes attributes of specific instances of products

Fulfillment (buying and refunding)
----------------------------------

Great now the product class exists and you can make new products but how
do you buy and refund that product?

Adding a Product to the Basket Page
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All products are purchased through the basket page and any product or set of products can be added to the basket page like so:

-  To add single product to basket page go to this url: http://localhost:18130/basket/add/?sku=\ <PRODUCT_SKU>

   -  *For example*: http://localhost:18130/basket/add/?sku=E2ADB40
   -  *For context*: the course about page’s purchase button links to the basket page with that course’s sku filled in

-  To add multiple products to basket page go to this url: http://localhost:18130/basket/add/?sku=<PRODUCT_1_SKU>&sku=<PRODUCT_2_SKU>
      
   -  *For example*: http://localhost:18130/basket/add/?sku=E2ADB40&sku=9BCCF4A
   -  *For context*: on the program about page, the purchase button links to the basket page with all of the course skus for that program in filled in

Fulfillment
~~~~~~~~~~~
How does oscar/ecommerce know how to fulfill a journal properly?

-  Register the journal fulfillment modules in the `oscar settings`_

   -  Add ``JournalFulfillmentModule`` to ``FulfillmentModules``

-  Each item in the basket is considered a ``line`` item.  Line items are supported by different fulfilment modules.  If a user is purchasing a line item supported by the journal fulfillment module the ``fulfill_product`` method will be called:  `journal fulfillment module`_

   -  Specifically for journals we make a POST request to the journal service ``journalaccess`` api.

      - The ``journal access`` api takes a user name and a journal id and grants access for that user to that journal.  For more info checkout the `journals repo`_
      -  We call that api in the ``post_journal_access`` method in `journal client`_

Refunds
~~~~~~~

-  There are two ways a refund is initiated generally

   -  The user initiates a refund through their dashboard

      -  This functionality does not exist for journals yet, it does exist for course seats and entitlements
      -  There are policy rules around this for course seats and entitlements, not for journals yet. The policy controls things like how long since purchase can you request a refund.

   -  A refund is requested through the oscar dashboard.  

      - From the user's perspective they will contact support and support will initiate the request through the oscar UI.
      - To make a refund for a specific order: http://localhost:18130/dashboard/orders/
      - When you click ``Approve Credit and Revoke`` the refund is initiated

-  What happens when a refund is initiated?

   -  Very similar to fulfillment, but instead the method ``revoke_line`` is called in the `journal fulfillment module`_
   -  For journals, when ``revoke_line`` is called we make a POST request to the ``journalaccess`` api but ``revoke_access`` to ``true``
   -  We call that api in the ``revoke_journal_access`` in `journal client`_


Journal Bundle Offers
=====================

**Journal Bundles** are a way to associate specific journals and specific
courses so that discounts can be applied when users buy them together.

**Offers** are an oscar concept, they allow you to create discounts in the
checkout basket if certain conditions are met.

Actually creating a journal bundle is done through the discovery django
admin, but creating a discount associated with that journal bundle is
done through the journal bundle offer page hosted in ecommerce.


How to create new journal bundle offers
---------------------------------------

-  First, you must have created a journal bundle in the discovery admin:

   -  Go to: http://localhost:18381/admin/journal/journalbundle/
   -  Click: ``ADD JOURNAL BUNDLE +``
   -  Fill in appropriate fields for your journal bundle
   -  Click: ``SAVE``

-  Create journal bundle offer

   -  Go to Journal Offers Dashboard: http://localhost:18130/journal/offers/
   -  Click: ``Create Journal Bundle Offer``
   -  Fill in the fields

      -  *Note*: ``Journal Bundle UUID`` can be found in the discovery django admin:  http://localhost:18381/admin/journal/journalbundle/

How do Offers Work?
-------------------

Just like products, offers can be created through the oscar dashboard (http://localhost:18130/dashboard/offers/), but we have created a different UI for our offers. All edx offers work pretty similarly:

-  The UI is made up of two templates that are basically copied between program, enterprise and journal offers

   -  Page listing all of the current journal offers: `journaloffer_list`_
   -  Form where you can create new journal offers: `journaloffer_form`_
    
-  The views controling these UIs can be found here: `journal views`_

   -  This calls the discovery api which fetches and caches the journal bundles: see ``fetch_journal_bundles`` in `journal client`_

-  Important tables related to offers:

   -  ``offer_conditionaloffer``: an instance of a conditional offer
   -  ``offer_condition``: the condition that must be met for an offer
   -  ``offer_benefit``: the benefit that will be applied to a given offer

Creating a new instance of a Journal Product
============================================

Because ecommerce and discovery need to have knowledge of journal
products, we have a management command to run that will update each
service.

These steps assume you have already provisioned journals on your local machine. If you have not, follow these steps: https://github.com/edx/journals

-  Change the ecommerce domain name to ``edx.devstack.ecommerce:18130``: http://localhost:18130/admin/sites/site/

   -  This is obviously not ideal currently there is a ticket on the backlog tracking this issue

-  In journals directory run: ``make app-shell``
-  To create a journal run: ``python manage.py publish_journals --create "<journal title>" --org "<partner org>" --price "<price>"``

   -  *For example*: ``python manage.py publish_journals --create "One Thousand Magical Herbs and Fungi" --org "edX" --price "42.00"``

-  Change the ecommerce domain name back to to ``localhost:18130``: http://localhost:18130/admin/sites/site/

That management command, ``publish_journals``, creates a journal in the journal service and creates an instance of a journal product in ecommerce. It does this by using this API that we made: http://localhost:18130/journal/api/v1/journals/


Future work
===========

Must happen before MVP release of Journals (All have been captured in jira tickets):
------------------------------------------------------------------------------------

-  Journal fulfillment should be async, just like seat fulfillments are today
-  Make sure that journals is not over using atomic transactions in its fulfillment or refund
-  Set up error monitoring for journal fulfilment

V2 release of Journals - It is a requirement that these issues are dealt with if journals remains in the code (All captured in jira tickets):
--------------------------------------------------------------------------------------------------------------------------------------------------

-  User initiated refunds: Currently refunds can only be initiated via the oscar dashboard. Practically, this means that a user can only get a refund by contacting support. Support then has to request the refund through the oscar dashboard. Remaining work for refunds includes:

   -  Creating a UI for users to request their own refunds
   -  Create a policy the controls when a user can and cannot request a refund

-  Fix bug where you have to change your ecommerce site host name in order to run the ``publish_journals`` management command

Suggested Improvements to the Ecommerce that are not specifically related to Journals:
--------------------------------------------------------------------------------------

-  Creating a product requires a bunch of boilerplate code, and it is not ideal that we need to have to use migrations for this. Ideally, we would have a config file with the list of products we want to install and new products like Journals would be plug-inable. Discovery work is required to determine what a good approach for this would be.
-  The journal offer templates are all basically copied from program and enterprise offers - which is obviously not ideal we should probably have a way for this to be more generic for any type of offer.
-  There should be a generic idea of bundling.
-  The way offers works is that every time a basket page loads it goes through every conditional offer in the ``offer_conditionaloffer`` table and checks if the conditions of said offer are met. This can be a huge performance hit especially as the number of program, enterprise and journal offers grow



.. _journals repo: https://github.com/edx/journals
.. _0031_journal_product_class: ../../extensions/catalogue/migrations/0031_journal_product_class.py
.. _oscar settings: ../../settings/_oscar.py
.. _journal fulfillment module: ../fulfillment/modules.py
.. _journal client: ../client.py
.. _journal views: ../views.py
.. _journaloffer_list: ../templates/journal/journaloffer_list.html
.. _journaloffer_form: ../templates/journal/journaloffer_form.html
