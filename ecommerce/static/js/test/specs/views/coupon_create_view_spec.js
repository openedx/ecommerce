define([
        'jquery',
        'views/coupon_create_edit_view',
        'views/alert_view',
        'models/coupon_model'
    ],
    function ($,
              CouponCreateEditView,
              AlertView,
              Coupon) {
        'use strict';

        describe('coupon create view', function () {
            var view,
                model;

            beforeEach(function () {
                model = new Coupon();
                view = new CouponCreateEditView({ model: model, editing: false }).render();
            });

            it('should throw an error if submitted with blank fields', function () {
                var errorHTML = '<strong>Error!</strong> Please complete all required fields.';
                view.formView.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });

            it('should toggle fields', function () {
                // discount
                view.$el.find('[name=code_type]').val('discount').trigger('change');
                expect(visible('[name=price]')).toBe(false);
                expect(visible('[name=benefit_value]')).toBe(true);

                view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                expect(visible('[name=code]')).toBe(false);
                view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                expect(visible('[name=code]')).toBe(true);
                view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                expect(visible('[name=code]')).toBe(true);

                // enrollment
                view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                expect(visible('[name=price]')).toBe(true);
                expect(visible('[name=benefit_value]')).toBe(false);
                expect(visible('[name=code]')).toBe(false);

                // quantity
                view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                expect(visible('[name=quantity]')).toBe(true);
                view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                expect(visible('[name=quantity]')).toBe(false);
                view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                expect(visible('[name=quantity]')).toBe(false);

                function visible(selector) {
                    return !view.$el.find(selector).closest('.form-group').hasClass('hidden');
                }
            });

        });
    }
);
