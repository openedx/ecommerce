define([
    'collections/catalog_collection',
    'test/mock_data/catalogs'
],
    function(CatalogCollection,
             MockCatalogs) {
        'use strict';

        var collection,
            response = MockCatalogs;

        beforeEach(function() {
            collection = new CatalogCollection();
        });

        describe('Catalog collection', function() {
            describe('parse', function() {
                it('should fetch the next page of results', function() {
                    spyOn(collection, 'fetch').and.returnValue(null);
                    response.next = '/api/v2/catalogs/course_catalogs/?page=2';

                    collection.parse(response);
                    expect(collection.fetch).toHaveBeenCalledWith(
                        {remove: false, url: '/api/v2/catalogs/course_catalogs/?page=2'}
                    );
                });
            });
        });
    }
);
