/* istanbul ignore next */
define([
    'collections/paginated_collection',
    'models/enterprise_customer_catalogs_model'
],
    function(PaginatedCollection, EnterpriseCustomerCatalogs) {
        'use strict';

        return PaginatedCollection.extend({
            model: EnterpriseCustomerCatalogs,
            url: '/api/v2/enterprise/customer_catalogs'
        });
    }
);
