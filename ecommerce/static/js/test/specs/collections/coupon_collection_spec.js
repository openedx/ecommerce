define([
        'collections/coupon_collection'
    ],
    function (CouponCollection) {
        'use strict';
        var collection,
            response = {
                count: 1,
                next: null,
                previous: null,
                results: [
                    {
                        id: 4,
                        url: 'http://localhost:8002/api/v2/products/4/',
                        structure: 'standalone',
                        product_class: 'Coupon',
                        title: 'Coupon',
                        price: '100.00',
                        expires: null,
                        attribute_values: [
                            {
                                name: 'Coupon vouchers',
                                value: [
                                    {
                                        id: 1,
                                        name: 'Coupon',
                                        code: 'P5KM74JY',
                                        usage: 'Single use',
                                        start_datetime: '2015-01-01T00:00:00Z',
                                        end_datetime: '2020-01-01T00:00:00Z',
                                        num_basket_additions: 1,
                                        num_orders: 0,
                                        total_discount: '0.00',
                                        date_created: '2015-12-09',
                                        offers: [
                                            1
                                        ]
                                    }
                                ]
                            }
                        ],
                        is_available_to_buy: true,
                        stockrecords: []
                    }
                ]
            };

        beforeEach(function () {
            collection = new CouponCollection();
        });

        describe('Coupon collection', function () {
            describe('parse', function () {
                it('should fetch the next page of results', function () {
                    spyOn(collection, 'fetch').and.returnValue(null);
                    response.next = '/api/v2/products/?page=2';

                    collection.parse(response);
                    expect(collection.url).toEqual(response.next);
                    expect(collection.fetch).toHaveBeenCalledWith({remove: false});
                });

            });
        });
    }
);
