define([
    'collections/product_collection',
    'test/spec-utils'
],
    function(ProductCollection,
              SpecUtils) {
        'use strict';

        var collection;

        describe('Product collection', function() {
            beforeEach(function() {
                collection = new ProductCollection();
            });

            describe('isValid', function() {
                it('should return true if the collection is empty', function() {
                    collection.reset();
                    expect(collection.isValid()).toEqual(true);
                });

                it('should return true if all models are valid', function() {
                    var ModelClass = SpecUtils.getModelForValidation(true);
                    collection.reset([new ModelClass(), new ModelClass()]);

                    expect(collection.isValid()).toEqual(true);
                });

                it('should return false if any of the models is NOT valid', function() {
                    var ModelClass = SpecUtils.getModelForValidation(false);
                    collection.reset([new ModelClass(), new ModelClass()]);

                    expect(collection.isValid()).toEqual(false);

                    // A mixture of validation statuses should always return false.
                    collection.add(new (SpecUtils.getModelForValidation(true))());
                    expect(collection.isValid()).toEqual(false);
                });
            });
        });
    }
);
