define([
        'jquery',
        'moment',
        'underscore',
        'models/coupon_model'
    ],
    function ($,
              moment,
              _,
              Coupon) {
        'use strict';

        var course = {
                id: 'a/b/c',
                type: 'verified',
                products: [
                    {
                        id: 9,
                        product_class: 'Seat',
                        certificate_type: 'verified',
                        attribute_values: [
                            {
                                name: 'certificate_type',
                                value: 'verified'
                            },
                            {
                                name: 'course_key',
                                value: 'edX/DemoX/Demo_Course'
                            },
                            {
                                name: 'id_verification_required',
                                value: true
                            }
                        ]
                    }
                ]
            },
            discount = {
                title: 'Test Discount',
                code_type: 'discount',
                client_username: 'test_client',
                start_date: '05/25/2016',
                end_date: '05/26/2017',
                stock_record_ids: [1],
                code: 'TESTCODE',
                voucher_type: 'Single use',
                quantity: 0,
                benefit_type: 'Percentage',
                benefit_value: 25,
                course_id: 'a/b/c',
                seat_type: 'verified',
                course: course
            },
            enrollment = {
                title: 'Test Enrollment',
                code_type: 'enrollment',
                client_username: 'test_client',
                start_date: '05/25/2016',
                end_date: '05/26/2017',
                stock_record_ids: [1],
                voucher_type: 'Single use',
                quantity: 0,
                price: 100,
                course_id: 'a/b/c',
                seat_type: 'verified',
                course: course
            };

        describe('Coupon model', function () {
            describe('validation', function () {
                it('should validate dates', function () {
                    spyOn($, 'ajax');
                    var model = new Coupon(discount);
                    model.validate();
                    expect(model.isValid()).toBeTruthy();

                    model.set('start_date', 'not a real date');
                    model.set('end_date', 'not a real date');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('start_date', '11/11/2015');
                    model.set('end_date', '10/10/2015');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate enrollment code has price', function () {
                    spyOn($, 'ajax');
                    var model = new Coupon(enrollment);
                    model.set('price', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate discount code has discount type and value', function () {
                    spyOn($, 'ajax');
                    var model = new Coupon(discount);
                    model.set('benefit_value', '');
                    model.set('benefit_type', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });
            });

            describe('save', function () {
                it('should POST enrollment data', function () {
                    spyOn($, 'ajax');
                    var model = new Coupon(enrollment);
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    var args = $.ajax.calls.argsFor(1)[0];
                    var ajaxData = JSON.parse(args.data);
                    expect(ajaxData.benefit_type).toEqual('Percentage');
                    expect(ajaxData.benefit_value).toEqual(100);
                    expect(ajaxData.quantity).toEqual(1);
                });

                it('should POST discount data', function () {
                    spyOn($, 'ajax');
                    var model = new Coupon(discount);
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    var args = $.ajax.calls.argsFor(1)[0];
                    var ajaxData = JSON.parse(args.data);
                    expect(ajaxData.price).toEqual(0);
                    expect(ajaxData.quantity).toEqual(1);
                });
            });

        });
});
