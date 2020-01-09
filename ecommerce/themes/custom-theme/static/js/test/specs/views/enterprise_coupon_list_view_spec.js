define([
    'jquery',
    'views/enterprise_coupon_list_view'
],
    function($, EnterpriseCouponListView) {
        'use strict';

        describe('coupon list view', function() {
            var view,
                coupons = {

                    recordsTotal: 2,
                    recordsFiltered: 2,
                    data: [
                        {
                            title: 'Test ENT Coupon 1',
                            client: 'Test Client 1',
                            code_status: 'ACTIVE',
                            enterprise_customer: {id: 'a96d51fa-8e50-4fc6-a7e2-14563c535c52'},
                            enterprise_customer_catalog: '3a8ba39b-11c9-49e2-908c-c8a719fd966e',
                            id: 1,
                            date_created: new Date()
                        },
                        {
                            title: 'Test ENT Coupon 2',
                            client: 'Test Client 1',
                            code_status: 'ACTIVE',
                            enterprise_customer: {id: 'f9b59bb3-7418-49cb-b40c-d78cd89b5d03'},
                            enterprise_customer_catalog: '0a2bd2b3-9c8a-4262-abe1-204c4d3af64f',
                            id: 2,
                            date_created: new Date()
                        }
                    ],
                    draw: 1
                };

            beforeEach(function() {
                spyOn($, 'ajax').and.callFake(function(params) {
                    params.success(coupons);
                });
                view = new EnterpriseCouponListView().render();
            });

            it('should change the default filter placeholder for coupon search field to a custom string', function() {
                expect(view.$el.find('#couponTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should populate the table based on the enterprise coupon api response', function() {
                var tableData = view.$el.find('#couponTable').DataTable().data();
                expect(tableData.data().length).toBe(coupons.data.length);
                expect(tableData.data().length).toBe(coupons.data.length);
            });
        });
    }
);
