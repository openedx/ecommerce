define([
    'jquery',
    'views/coupon_list_view'
],
    function($, CouponListView) {
        'use strict';

        describe('coupon list view', function() {
            var view,
                coupons = {
                    recordsTotal: 2,
                    recordsFiltered: 2,
                    data: [
                        {
                            title: 'Test Coupon 1',
                            category: {id: 3, name: 'Affiliate Promotion'},
                            code: 'H7SL19DH26PL07E',
                            client: 'Test Client 1',
                            id: 1,
                            date_created: new Date()
                        },
                        {
                            title: 'Test Coupon 2',
                            category: {id: 3, name: 'Affiliate Promotion'},
                            code: 'G7SL19ZZ26PL07E',
                            client: 'Test Client 2',
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
                view = new CouponListView().render();
            });

            it('should change the default filter placeholder for coupon search field to a custom string', function() {
                expect(view.$el.find('#couponTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should adjust the style of the coupon filter textbox', function() {
                var $tableInput = view.$el.find('#couponTable_filter input');

                expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();
            });

            it('should populate the table based on the coupon api response', function() {
                var tableData = view.$el.find('#couponTable').DataTable().data();
                expect(tableData.data().length).toBe(coupons.data.length);
            });
        });
    }
);
