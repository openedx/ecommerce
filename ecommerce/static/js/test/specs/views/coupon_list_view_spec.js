define([
    'jquery',
    'views/coupon_list_view',
    'collections/coupon_collection'
],
    function($, CouponListView, CouponCollection) {
        'use strict';

        describe('coupon list view', function() {
            var view,
                collection,
                coupons = [
                    {
                        category: {id: 3, name: 'Affiliate Promotion'},
                        code: 'G7SL19ZZ26PL07E',
                        course_seats: [],
                        course_seat_types: [],
                        id: 1,
                        max_uses: 2,
                        price: 10,
                        quantity: 1,
                        seats: [],
                        stock_record_ids: [],
                        total_value: 10,
                        date_created: new Date()
                    },
                    {
                        category: {id: 3, name: 'Affiliate Promotion'},
                        code: 'G7SL19ZZ26PL07E',
                        course_seats: [],
                        course_seat_types: [],
                        id: 1,
                        max_uses: 2,
                        price: 10,
                        quantity: 2,
                        seats: [],
                        stock_record_ids: [],
                        total_value: 20,
                        date_created: new Date()
                    }
                ];

            beforeEach(function() {
                collection = new CouponCollection();
                collection.set(coupons);

                view = new CouponListView({collection: collection}).render();
            });

            it('should change the default filter placeholder for coupon search field to a custom string', function() {
                expect(view.$el.find('#couponTable_filter input[type=search]').attr('placeholder')).toBe('Search...');
            });

            it('should adjust the style of the coupon filter textbox', function() {
                var $tableInput = view.$el.find('#couponTable_filter input');

                expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();
            });

            it('should populate the table based on the coupon collection', function() {
                var tableData = view.$el.find('#couponTable').DataTable().data();
                expect(tableData.data().length).toBe(collection.length);
            });
        });
    }
);
