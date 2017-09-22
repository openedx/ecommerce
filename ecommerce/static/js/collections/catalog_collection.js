define([
    'collections/paginated_collection',
    'models/catalog_model'
],
    function(PaginatedCollection,
              Catalog) {
        'use strict';

        return PaginatedCollection.extend({
            model: Catalog,
            url: '/api/v2/catalogs/course_catalogs/'
        }
        );
    }
);
