define([
    'collections/coupon_collection',
    'test/mock_data/coupons'
],
    function(CouponCollection,
              MockCoupons) {
        'use strict';

        var collection,
            response = MockCoupons.couponAPIResponseData;

        beforeEach(function() {
            collection = new CouponCollection();
        });

        describe('Coupon collection', function() {
            describe('parse', function() {
                it('should fetch the next page of results', function() {
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
