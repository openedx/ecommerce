define([
    'jquery',
    'utils/utils',
    'views/enterprise_coupon_create_edit_view',
    'views/alert_view',
    'models/enterprise_coupon_model',
    'test/mock_data/categories',
    'test/mock_data/enterprise_customers',
    'test/mock_data/coupons',
    'ecommerce'
],
    function($,
              Utils,
              EnterpriseCouponCreateEditView,
              AlertView,
              EnterpriseCoupon,
              MockCategories,
              MockCustomers,
              MockCoupons,
              ecommerce) {
        'use strict';

        describe('coupon create view', function() {
            var view,
                model;

            beforeEach(function() {
                ecommerce.coupons = {
                    categories: MockCategories,
                    enterprise_customers: MockCustomers
                };
                model = new EnterpriseCoupon();
                view = new EnterpriseCouponCreateEditView({model: model, editing: false}).render();
                spyOn(model, 'save');
            });

            it('should submit enterprise coupon form with valid fields', function() {
                view.$('[name=title]').val('Test Enrollment').trigger('change');
                view.$('[name=code_type]').val('Enrollment code').trigger('change');
                view.$('[name=start_date]').val('2015-01-01T00:00').trigger('change');
                view.$('[name=end_date]').val('2016-01-01T00:00').trigger('change');
                view.$('[name=category]').val('4').trigger('change');
                view.$('[name=enterprise_customer]').val('42a30ade47834489a607cd0f52ba13cf').trigger('change');
                view.$('[name=enterprise_customer_catalog]').val('ec6a900a13c74f2abdb0b9bd9415ed78').trigger('change');
                view.$('#not-applicable').prop('checked', true).trigger('change');
                view.formView.submit($.Event('click'));
                expect(model.isValid()).toBe(true);
                expect(model.save).toHaveBeenCalled();
            });
        });

        describe('coupons edit view', function() {
            var view,
                model,
                enterpriseCouponModelData = MockCoupons.enterpriseCouponModelData;

            describe('edit enrollment code', function() {
                beforeEach(function() {
                    enterpriseCouponModelData.enterprise_customer = MockCustomers[0].id;
                    model = EnterpriseCoupon.findOrCreate(enterpriseCouponModelData, {parse: true});
                    view = new EnterpriseCouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display coupon details in form fields', function() {
                    var voucherType = view.$el.find('[name=voucher_type]'),
                        startDate = Utils.stripTimezone(model.get('start_date')),
                        endDate = Utils.stripTimezone(model.get('end_date'));
                    expect(view.$el.find('[name=title]').val()).toEqual(model.get('title'));
                    expect(view.$el.find('[name=code_type]').val()).toEqual('Enrollment code');
                    expect(view.$el.find('[name=start_date]').val()).toEqual(startDate);
                    expect(view.$el.find('[name=end_date]').val()).toEqual(endDate);
                    expect(voucherType.children().length).toBe(4);
                    expect(voucherType.val()).toEqual(model.get('voucher_type'));
                    expect(view.$el.find('[name=quantity]').val()).toEqual(model.get('quantity').toString());
                    expect(view.$el.find('[name=enterprise_customer]').val()).toEqual(
                        model.get('enterprise_customer').id
                    );
                    expect(view.$el.find('[name=enterprise_customer_catalog]').val()).toEqual(
                        model.get('enterprise_customer_catalog')
                    );
                });
            });
        });
    }
);
