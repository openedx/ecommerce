=====================================
Journal Service Ecommerce Integration
=====================================

The Journal Product enables organizations to provide educational
resources that are better surfaced outside of the course experience. For
more information on this service and to see the source code go here:
https://github.com/edx/journals

This module contains the necessary integrations to make the journal
product purchasable.

New Product Class for Journals
==============================

A product class is a type of product, like “course seat” or “course
entitlement”. A new product class is created for journals by running
<MIGRATION>. This writes a new row to the <product class table>

Fulfillment
-----------

Orders are fulfilled by making a call to the journal service’s
<journalaccess> api.

-  Method called when a journal order is fulfilled: <>

-  Method invoked to call <journalaccess> api:

Refunds
-------

Refunds are initiated via the oscar dashboard. Behind the scenes it’s
calling the journal service’s <journalaccess> api with the <is_refund>
field set to <true>

-  Method called when a journal order is refunded: <>

-  Method invoked to the journal refund api: <>

Journal Bundles Offers
======================

Journal Bundles are a way to associate specific journals and specific
courses so that discounts can be applied when users buy them together.
Actually creating a journal bundle is done through the discovery django
admin, but creating a discount associated with that journal bundle is
done through the journal bundle off page hosted in ecommerce.

Journal Bundle Offers Dashboard
-------------------------------

This is where staff users can create new journal bundle offers.

How to create new journal bundle offers:

-  First, you must have created a journal bundle in the discovery admin:

   -  Go to: http://localhost:18381/admin/journal/journalbundle/

   -  Click: “ADD JOURNAL BUNDLE +”

   -  Fill in appropriate fields for your journal bundle

   -  Click: “SAVE”

-  Create journal bundle offer

   -  Go to Journal Offers Dashboard:
         http://localhost:18130/journal/offers/

   -  Click: “Create Journal Bundle Offer”

   -  Fill in the fields

      -  “Journal Bundle UUID” can be found in the discovery django
            admin: http://localhost:18381/admin/journal/journalbundle/

API Endpoint to Create and Update Journal Products
--------------------------------------------------

This api endpoint allows ecommerce to be updated on new journals and
their price and a few other attributes important to ecommerce.

-  Api Endpoint: http://localhost:18130/journal/api/v1/journals

Remaining Work
==============

User initiated refunds
----------------------

Currently refunds can only be initiated via the oscar dashboard.
Practically, this means that a user can only get a refund by contacting
support. Support then has to request the refund through the oscar
dashboard. Remaining work for refunds includes:

-  Creating a UI for users to request their own refunds

-  Create a policy the controls when a user can and cannot request
      refunds

Places where the Journal code spills into the main ecommerce code
-----------------------------------------------------------------

All places where the journal code is not contained in its own module has
been commented with <# TODO: journal dependency>
