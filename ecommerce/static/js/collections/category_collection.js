define([
    'collections/paginated_collection',
    'models/category'
],
    function(PaginatedCollection,
              Category) {
        'use strict';

        return PaginatedCollection.extend({
            model: Category,
            url: '/api/v2/coupons/categories/'
        }
        );
    }
);
