define([
        'collections/paginated_collection',
        'models/program_model'
    ],
    function (PaginatedCollection,
              Program) {
        'use strict';

        return PaginatedCollection.extend({
            model: Program,
            url: '/api/v2/programs/'
        });
    }
);
