define([
    'jquery',
    'views/enterprise_coupon_list_view',
    'collections/enterprise_coupon_collection'
],
    function($, EnterpriseCouponListView, EnterpriseCouponCollection) {
        'use strict';

        describe('coupon list view', function() {
            var view,
                collection,
                coupons = [
                    {
                        category: {id: 3, name: 'Affiliate Promotion'},
                        code: 'G7SL19ZZ26PL07E',
                        enterprise_customer: {id: 'a96d51fa-8e50-4fc6-a7e2-14563c535c52'},
                        enterprise_customer_catalog: '3a8ba39b-11c9-49e2-908c-c8a719fd966e',
                        id: 1,
                        max_uses: 2,
                        quantity: 1,
                        date_created: new Date()
                    },
                    {
                        category: {id: 3, name: 'Affiliate Promotion'},
                        code: 'FOIEH89WEHISEF9',
                        enterprise_customer: {id: 'f9b59bb3-7418-49cb-b40c-d78cd89b5d03'},
                        enterprise_customer_catalog: '0a2bd2b3-9c8a-4262-abe1-204c4d3af64f',
                        id: 2,
                        max_uses: 2,
                        quantity: 2,
                        date_created: new Date()
                    }
                ];

            beforeEach(function() {
                collection = new EnterpriseCouponCollection();
                collection.set(coupons);

                view = new EnterpriseCouponListView({collection: collection}).render();
            });

            it('should change the default filter placeholder for coupon search field to a custom string', function() {
                expect(view.$el.find('#couponTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should populate the table based on the coupon collection', function() {
                var tableData = view.$el.find('#couponTable').DataTable().data();
                expect(tableData.data().length).toBe(collection.length);
            });
        });
    }
);
