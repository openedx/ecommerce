define([
    'jquery',
    'models/enterprise_coupon_model',
    'models/coupon_model',
    'test/mock_data/coupons'
],
    function($,
             EnterpriseCoupon,
             Coupon,
             MockCoupons) {
        'use strict';

        var enterpriseCouponData = MockCoupons.enterpriseCouponModelData;

        describe('Coupon model', function() {
            describe('url', function() {
                it('should be /api/v2/enterprise/coupons/ for new instances', function() {
                    var instance = new EnterpriseCoupon();
                    expect(instance.url()).toEqual('/api/v2/enterprise/coupons/');
                });

                it('should have a trailing slash for existing instances', function() {
                    var id = 1,
                        instance = new EnterpriseCoupon({id: id});
                    expect(instance.url()).toEqual('/api/v2/enterprise/coupons/' + id + '/');
                });
            });

            describe('validation', function() {
                var model;

                beforeEach(function() {
                    spyOn($, 'ajax');
                    model = EnterpriseCoupon.findOrCreate(enterpriseCouponData, {parse: true});
                });
                it('it should validate with valid data', function() {
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate enterprise customer is required', function() {
                    model.set('enterprise_customer', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate enterprise customer catalog is required', function() {
                    model.set('enterprise_customer_catalog', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate notify email is correct', function() {
                    model.set('notify_email', 'batman');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate sales_force_id is correct', function() {
                    model.set('sales_force_id', 'Invalid_ID');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate sales_force_id with "none" value', function() {
                    model.set('sales_force_id', 'none');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate sales_force_id is required', function() {
                    model.set('sales_force_id', '');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate salesforce_opportunity_line_item is correct', function() {
                    model.set('salesforce_opportunity_line_item', 'Invalid_ID');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });

                it('should validate salesforce_opportunity_line_item with "none" value', function() {
                    model.set('salesforce_opportunity_line_item', 'none');
                    model.validate();
                    expect(model.isValid()).toBeTruthy();
                });

                it('should validate salesforce_opportunity_line_item is required', function() {
                    model.set('salesforce_opportunity_line_item', '');
                    model.validate();
                    expect(model.isValid()).toBeFalsy();
                });
            });

            describe('save', function() {
                it('should POST enrollment data', function() {
                    var model, args, ajaxData;
                    spyOn($, 'ajax');
                    model = EnterpriseCoupon.findOrCreate(enterpriseCouponData, {parse: true});
                    model.save();
                    expect($.ajax).toHaveBeenCalled();
                    args = $.ajax.calls.argsFor(0);
                    ajaxData = JSON.parse(args[0].data);
                    expect(ajaxData.enterprise_customer).toEqual(enterpriseCouponData.enterprise_customer);
                    expect(ajaxData.enterprise_customer_catalog)
                        .toEqual(enterpriseCouponData.enterprise_customer_catalog);
                    expect(ajaxData.notify_email).toEqual(enterpriseCouponData.notify_email);
                    expect(ajaxData.contract_discount_value).toEqual(enterpriseCouponData.contract_discount_value);
                    expect(ajaxData.prepaid_invoice_amount).toEqual(enterpriseCouponData.prepaid_invoice_amount);
                    expect(ajaxData.benefit_type).toEqual('Percentage');
                    expect(ajaxData.benefit_value).toEqual(100);
                });

                it('should call Coupon model when saved', function() {
                    var model = EnterpriseCoupon.findOrCreate(enterpriseCouponData, {parse: true}),
                        title = 'Coupon title';
                    spyOn(Coupon.prototype, 'save');
                    model.save(
                        {title: title},
                        {patch: true}
                    );

                    expect(Coupon.prototype.save).toHaveBeenCalledWith(
                        {title: title},
                        {patch: true}
                    );
                });
            });
        });
    });
