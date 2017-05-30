define([
    'collections/paginated_collection',
    'models/enterprise_customer_model'
],
    function(PaginatedCollection,
              EnterpriseCustomer) {
        'use strict';

        return PaginatedCollection.extend({
            model: EnterpriseCustomer,
            url: '/api/v2/enterprise/customers'
        });
    }
);
