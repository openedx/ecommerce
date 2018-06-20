=================================================================
Suggested Improvements to Ecommerce Listed in No Particular Order
=================================================================

-  Creating a product requires a bunch of boilerplate code, and it is not ideal that we need to have to use migrations for this. Ideally, we would have a config file with the list of products we want to install and new products would be plug-inable. Discovery work is required to determine what a good approach for this would be.
-  New offer templates are all basically copied from program and enterprise offers - which is obviously not ideal we should probably have a way for this to be more generic for any type of offer.
-  There should be a generic idea of bundling.
-  The way offers works is that every time a basket page loads it goes through every conditional offer in the ``offer_conditionaloffer`` table and checks if the conditions of said offer are met. This can be a huge performance hit especially as the number of offers grow
- On the admin page to create offers: Every page iterates through every conditional offer. For example, the page listing enterprise offers (http://localhost:18130/enterprise/offers/) iterates through all program *and* enterprise *and* any other offers we add to generate that page. This is a performance hit.