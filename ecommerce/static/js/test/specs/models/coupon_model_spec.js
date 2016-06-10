define([
        'jquery',
        'moment',
        'underscore',
        'models/coupon_model',
        'test/mock_data/coupons'
    ],
    function ($,
              moment,
              _,
              Coupon,
              Mock_Coupons) {
        'use strict';

        var discountCodeData = Mock_Coupons.discountCodeCouponModelData,
            enrollmentCodeData = Mock_Coupons.enrollmentCodeCouponModelData;


        describe('Coupon model', function () {
            describe('validation', function () {
                var model;

                beforeEach(function () {
                    spyOn($, 'ajax');
                    model = Coupon.findOrCreate(discountCodeData, {parse: true});
                });

                it('should validate dates', function () {
                    model.validate();
                    expect(model.isValid()).toBeTruthy();

                    model.set('start_date', 'not a real date');
                    model.set('end_date', 'not a real date');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('start_date', '2015-11-11T00:00:00Z');
                    model.set('end_date', '2015-10-10T00:00:00Z');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate discount code has discount type and value', function () {
                    model.set('benefit_value', '');
                    model.set('benefit_type', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate course ID if the catalog is a Single Course Catalog', function () {
                    model.set('catalog_type', 'Single course');
                    model.set('course_id', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('course_id', 'a/b/c');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate seat type if the catalog is a Single Course Catalog', function () {
                    model.set('catalog_type', 'Single course');
                    model.set('seat_type', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('seat_type', 'Verified');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate catalog query and course seat types for Multiple Courses Catalog', function () {
                    model.set('catalog_type', 'Multiple courses');
                    model.set('catalog_query', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('catalog_query', '*:*');
                    model.set('course_seat_types', []);
                    model.validate();
                    expect(model.isValid()).toBeFalsy();

                    model.set('catalog_query', '*:*');
                    model.set('course_seat_types', ['verified']);
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });
            });

            describe('test model methods', function () {
                it('should return seat price if a coupon has a seat', function () {
                    var model = new Coupon();

                    expect(model.getSeatPrice()).toEqual('');

                    model.set('seats', [{'price': 100}]);
                    expect(model.getSeatPrice()).toEqual(100);
                });
            });

            describe('save', function () {
                it('should POST enrollment data', function () {
                    var model, args, ajaxData;
                    spyOn($, 'ajax');
                    model = Coupon.findOrCreate(enrollmentCodeData, {parse: true});
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    args = $.ajax.calls.argsFor(0);
                    ajaxData = JSON.parse(args[0].data);
                    expect(ajaxData.benefit_type).toEqual('Percentage');
                    expect(ajaxData.benefit_value).toEqual(100);
                    expect(ajaxData.quantity).toEqual(1);
                });

                it('should POST discount data', function () {
                    var model, args, ajaxData;
                    spyOn($, 'ajax');
                    model = Coupon.findOrCreate(discountCodeData, {parse: true});
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    args = $.ajax.calls.argsFor(0);
                    ajaxData = JSON.parse(args[0].data);
                    expect(ajaxData.quantity).toEqual(1);
                });
            });
        });
});
