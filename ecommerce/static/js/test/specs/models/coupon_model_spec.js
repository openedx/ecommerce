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
                it('should validate dates', function () {
                    spyOn($, 'ajax');
                    var model = Coupon.findOrCreate(discountCodeData, {parse: true});
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
                    spyOn($, 'ajax');
                    var model = Coupon.findOrCreate(discountCodeData, {parse: true});
                    model.set('benefit_value', '');
                    model.set('benefit_type', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
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
