define([
        'collections/coupon_category_collection'
    ],
    function (CouponCategoryCollection) {
        'use strict';
        var collection,
            response = {
                id: 3,
                children: [
                    {
                        id: 4,
                        children: [],
                        path: '00020001',
                        depth: 2,
                        numchild: 0,
                        name: 'Affiliate Promotion',
                        description: '',
                        image: null,
                        slug: 'affiliate-promotion'
                    }
                ]
            },
            parsedResponse = [
                {
                    value: 4,
                    label: 'Affiliate Promotion',
                    selected: true
                }
            ];

        beforeEach(function () {
            collection = new CouponCategoryCollection();
            spyOn(collection, 'fetch').and.returnValue(response);
            collection.fetch();
        });

        describe('Coupon category collection', function () {

            describe('[method] fetch', function(){
                it('should fetch the data from api', function(){
                    expect(collection.fetch).toHaveBeenCalled();
                    expect(collection.fetch()).toEqual(response);
                });
            });

            describe('[method] parse', function () {
                it('should return parsed response', function () {
                    expect(collection.parse(response)).toEqual(parsedResponse);
                });
            });

        });
    }
);
