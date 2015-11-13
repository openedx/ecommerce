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
                        id: 1,
                        title: 'Test Coupon',
                        client: 'TestClient',
                        price: 0.0,
                        vouchers: [
                            {
                                id: 8,
                                name: 'Voucher for 2: edx-Coupon',
                                code: 'CODE123',
                                usage: 'Single use',
                                start_datetime: '2015-11-22T05:00:00Z',
                                end_datetime: '2015-11-25T05:00:00Z',
                                num_basket_additions: 0,
                                num_orders: 0,
                                total_discount: '0.00',
                                date_created: '2015-11-24',
                                offers: [
                                    3
                                ]
                            }
                        ]
                    },
                ]
            };

        beforeEach(function () {
            collection = new CouponCollection();
        });

        describe('Coupon collection', function () {
            describe('parse', function () {
                it('should return the results list in the response', function () {
                    expect(collection.parse(response)).toEqual(response.results);
                });

                it('should fetch the next page of results', function () {
                    spyOn(collection, 'fetch').and.returnValue(null);
                    response.next = '/api/v2/coupons/?page=2';

                    collection.parse(response);
                    expect(collection.url).toEqual(response.next);
                    expect(collection.fetch).toHaveBeenCalledWith({remove: false});
                });
            });
        });
    }
);
