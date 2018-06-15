=====================================
Journal Service Ecommerce Integration
=====================================

The Journal Product enables organizations to provide educational
resources that are better surfaced outside of the course experience. For
more information and to see the source code checkout the journals repo:
https://github.com/edx/journals

This module contains the necessary integrations to make the journals
product purchasable. It is also a rough primer on some important basics
of how edx-ecommerce works.

A New Journal Product Class
===========================

Oscar has a concept ‘product class’ (in the Oscar UI it’s referred to as
‘product type’). This is just a type of product, like “course seat” or
“course entitlement”.

Creating a New Product Class
----------------------------

-  New product classes can be made manually through the oscar dashboard:
      http://localhost:18130/dashboard/catalogue/product-types/

-  But we want that product type to exist even if we reprovision
      ecommerce, and we want the Journals product class to exist on
      every environment without manual intervention.

-  So we manually make a migration:
      ecommerce/extensions/catalogue/migrations/0031_journal_product_class.py

   -  This migration writes a new row to the \`catalogue_productclass\`
         table, creating the product class ‘Journal’

   -  It also writes a row to the \`catalogue_productattribute\` table,
         which specifies that the product class ‘Journal’ has an
         attribute ‘UUID’

-  Important tables that define a product in oscar

   -  \`catalogue_productclass`: defines types of products

   -  \`catalogue_productattribute`: defines a set of attributes for a
         given product type

      -  Ex. the ‘Journal’ product class has one product attribute
            associated with it; that is UUID. Other products have
            multiple attributes.

      -  Again, this could be done through the oscar UI, but we do this
            through migrations to make sure that it persists through
            provisions:
            http://localhost:18130/dashboard/catalogue/product-type/6/update/#product_attributes

   -  \`catalogue_product`: describes an instance of a product

      -  Ex. You may have the product class ‘course seat’, but an
            instance of that product may be ‘seat in course DemoX’

      -  You can create a new product through the dashboard:
            http://localhost:18130/dashboard/catalogue/

      -  We do not create journals through the oscar dashboard, see
            ##Creating New Instances of JOurnals

   -  \`catalogue_productattributevalue`: describes attributes of
         specific instances of products

Fulfillment (buying and refunding)
----------------------------------

Great now the product class exists and you can make new products but how
do you buy and refund that product?

Adding a Product to the Basket Page
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All products are purchased through the basket page

-  Any product or set of products can be added to the basket page like
      so:

   -  Add single product to basket page:

      -  http://localhost:18130/basket/add/?sku=\ <PRODUCT_SKU>

      -  Ex. http://localhost:18130/basket/add/?sku=E2ADB40

      -  For context, the course about page’s purchase button links to
            the this basket page with that course’s sku filled in

   -  Add multiple products to basket page:

      -  http://localhost:18130/basket/add/?sku=<PRODUCT_SKU>&sku=<PRODUCT_SKU>

      -  Ex. http://localhost:18130/basket/add/?sku=E2ADB40&sku=9BCCF4A

      -  For context: on the program about page, the purchase button
            just links to the basket page with all of the course skus
            for that program in filled in

Fulfillment
~~~~~~~~~~~

-  How does oscar/ecommerce know how to fulfill a journal properly?

   -  Register the journal fulfillment modules in the oscar settings:

      -  Link to oscar settings file: ecommerce/settings/_oscar.py

      -  Add \`JournalFulfillmentModule\` to \`FulfillmentModules\`

   -  If that line is supported by this fulfillment module it will be
         fulfilled by the \`fulfill_product\` method:
         https://github.com/edx/ecommerce/blob/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/fulfillment/modules.py#L32

   -  Specifically for journals we make a POST request to the journal
         service \`journalaccess\` api.

      -  The journal access api takes a user and a journal and grants
            access for that user to that journal

      -  We call that api in \`post_journal_access`:
            https://github.com/edx/ecommerce/blob/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/client.py#L25

Refunds
~~~~~~~

-  There are basically two ways a refund is initiated generally

   -  User initiates a refund through their dashboard

      -  This functionality does not exist for journals yet, it does
            exist for course seats and entitlements

      -  There are policy rules around this for course seats and
            entitlements, not for journals yet (i.e. how long since
            purchase can you request a refund)

   -  A refund is requested through the oscar dashboard (support does
         this @edX)

      -  Make a refund for a specific order:
            http://localhost:18130/dashboard/orders/

      -  When you hit \`Approve Credit and Revoke\` the refund is called

-  What happens when a refund is initiated?

   -  Very similar to fulfillment, but instead it calls \`revoke_line`:
         https://github.com/edx/ecommerce/blob/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/fulfillment/modules.py#L88

   -  For journals we are making a POST request to \`journalaccess\` api
         but with \`revoke_access\` to \`true\`

      -  We call that in \`revoke_journal_access`:
            https://github.com/edx/ecommerce/blob/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/client.py#L47

Journal Bundle Offers
---------------------

*Journal Bundles* are a way to associate specific journals and specific
courses so that discounts can be applied when users buy them together.

*Offers* are an oscar concept, they allow you to create discounts in the
checkout basket if certain conditions are met.

Actually creating a journal bundle is done through the discovery django
admin, but creating a discount associated with that journal bundle is
done through the journal bundle offer page hosted in ecommerce.

How to create new journal bundle offers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

      -  Note: \`Journal Bundle UUID\` can be found in the discovery
            django admin:
            http://localhost:18381/admin/journal/journalbundle/

How do Offers Work?
-------------------

-  All offers work pretty similar

   -  The UI:

      -  Page listing all of the current journal offers:
            `ecommerce <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e>`__/`ecommerce <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce>`__/`journal <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal>`__/`templates <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/templates>`__/`journal <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/templates/journal>`__/journaloffer_list.html

      -  Form where you can create new journal offers:
            `ecommerce <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e>`__/`ecommerce <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce>`__/`journal <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal>`__/`templates <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/templates>`__/`journal <https://github.com/edx/ecommerce/tree/3f3f348e1e13f1d587ab1d7b8ed712735c1f6d6e/ecommerce/journal/templates/journal>`__/journaloffer_form.html

      -  These templates are all basically copied from program and
            enterprise offers - which is obviously not ideal we should
            probably have a way for this to be more generic for any type
            of offer.

   -  Viewing the journal offer list:

      -  JournalOfferViewList: ecommerce/journal/views.py

      -  This calls the discovery api which fetches and caches the
            journal bundles: fetch_journal_bundles [LINK TO FILE]

   -  Important tables related to offers:

      -  \`offer_conditionaloffer`: an instance of a conditional offer

      -  \`offer_condition`: the condition that must be met for an offer

      -  \`offer_benefit`: the benefit that will be applied to a given
            offer

Creating a new instance of a Journal Product:
---------------------------------------------

Because ecommerce and discovery need to have knowledge of journal
products, we have a management command to run that will update each
service.

-  Steps assume you have already provisioned journals on your local
      machine. If you have not, follow these steps:
      https://github.com/edx/journals

-  Change the ecommerce domain name to \`edx.devstack.ecommerce:18130\`
      : http://localhost:18130/admin/sites/site/

   -  This is obviously not ideal currently there is a ticket on the
         backlog tracking this issue

-  In journals directory run: \`make app-shell\`

-  \`python manage.py publish_journals --create "<journal title>" --org
      "<partner org>" --price "<price>"\`

   -  Ex: \`python manage.py publish_journals --create "One Thousand
         Magical Herbs and Fungi" --org "edX" --price "42.00"\`

-  Change the ecommerce domain name back to to \`localhost:18130\` :
      http://localhost:18130/admin/sites/site/

That management command, \`publish_journals`, creates a journal in the
journal service and creates an instance of a journal product in
ecommerce. It does this by using this API that we made:
http://localhost:18130/journal/api/v1/journals/

Future work
===========

Must happen before MVP release of Journals:
-------------------------------------------

-  Journal fulfillment should be async, just like seat fulfillments are
      today

-  Make sure that journals is not over using atomic transactions in its
      fulfillment or refund

-  Set up error monitoring for journal fulfilment

V2 release of Journals (What must happen for Journals to be a maintainable product going forward):
--------------------------------------------------------------------------------------------------

-  User initiated refunds: Currently refunds can only be initiated via
      the oscar dashboard. Practically, this means that a user can only
      get a refund by contacting support. Support then has to request
      the refund through the oscar dashboard. Remaining work for refunds
      includes:

   -  Creating a UI for users to request their own refunds

   -  Create a policy the controls when a user can and cannot request a
         refund

-  Fix bug where you have to change your ecommerce site host name in
      order to run the \`publish_journals\` management command

Suggested Improvements to the Ecommerce that are not specifically related to Journals:
--------------------------------------------------------------------------------------

-  Creating a product requires a bunch of boilerplate code, and it is
      not ideal that we need to have to use migrations for this.
      Ideally, we would have a config file with the list of products we
      want to install and new products like Journals would be
      plug-inable. Discovery work is required to determine what a good
      approach for this would be.

-  The journal offer templates are all basically copied from program and
      enterprise offers - which is obviously not ideal we should
      probably have a way for this to be more generic for any type of
      offer.

-  There should be a generic idea of bundling.

-  The way offers works is that every time a basket page loads it goes
      through every conditional offer in the \`offer_conditionaloffer\`
      table and checks if the conditions of said offer are met. This can
      be a huge performance hit especially as the number of program,
      enterprise and journal offers grow
