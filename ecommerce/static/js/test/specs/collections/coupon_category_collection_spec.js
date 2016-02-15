define([
        'collections/coupon_category_collection'
    ],
    function (CouponCategoryCollection) {
        'use strict';
        var collection,
            response = {
                id: 3,
                name: 'Coupons',
                slug: 'coupons',
                description: 'All Coupons',
                path: '0002',
                depth: 1,
                numchild: 9,
                image: null,
                child: [
                    {
                        id: 4,
                        name: 'NewCoursePromo',
                        slug: 'newcoursepromo',
                        description: '',
                        path: '00020001',
                        depth: 2,
                        numchild: 1,
                        image: null,
                        child: [
                            {
                                id: 17,
                                name: 'None',
                                slug: 'none',
                                description: '',
                                path: '000200010001',
                                depth: 3,
                                numchild: 0,
                                image: null,
                                child: []
                            }
                            ]
                    }
                ]
            },
            parsedResponse = [
                {
                    value: 4,
                    label: 'NewCoursePromo',
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
