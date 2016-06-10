define([
        'jquery',
        'underscore',
        'views/coupon_form_view',
        'views/alert_view',
        'models/coupon_model',
        'test/mock_data/categories',
        'test/mock_data/coupons',
        'ecommerce'
    ],
    function ($,
              _,
              CouponFormView,
              AlertView,
              Coupon,
              Mock_Categories,
              Mock_Coupons,
              ecommerce) {
        'use strict';

        describe('coupon form view', function () {
            var view,
                model,
                courseData = Mock_Coupons.courseData;

            /**
              * Helper function to check if a form field is shown.
              */
            function visible(selector) {
                var formGroup = view.$el.find(selector).closest('.form-group');
                if (formGroup.length > 0) {
                    return !formGroup.hasClass('hidden');
                } else {
                    return false;
                }
            }

            beforeEach(function () {
                ecommerce.coupons = {
                    categories: Mock_Categories
                };
                model = new Coupon();
                view = new CouponFormView({ editing: false, model: model }).render();
            });

            describe('seat type dropdown', function () {

                var courseId = 'course-v1:edX+DemoX+Demo_Course',
                    seatType;

                beforeEach(function () {
                    jasmine.clock().install();
                    seatType = view.$el.find('[name=seat_type]');
                    spyOn($, 'ajax').and.callFake(function (options) {
                        options.success(courseData);
                    });
                    view.$el.find('[name=course_id]').val(courseId).trigger('input');
                    // event is debounced, override _.now to trigger immediately
                    spyOn(_, 'now').and.returnValue(Date.now() + 110);
                    jasmine.clock().tick(110);
                });

                afterEach(function () {
                    jasmine.clock().uninstall();
                });

                it('should fill seat type options from course ID', function () {
                    expect($.ajax).toHaveBeenCalled();
                    expect(seatType.children().length).toBe(2);
                    expect(seatType.children()[0].innerHTML).toBe('Verified');
                    expect(seatType.children()[1].innerHTML).toBe('Honor');
                });

                it('should set stock_record_ids from seat type', function () {
                    seatType.children()[0].selected = true;
                    seatType.trigger('change');
                    expect(model.get('stock_record_ids')).toEqual([2]);
                });

                it('changeTotalValue should call updateTotalValue', function () {
                    spyOn(view, 'updateTotalValue');
                    spyOn(view, 'getSeatData');
                    view.changeTotalValue();
                    expect(view.updateTotalValue).toHaveBeenCalled();
                    expect(view.getSeatData).toHaveBeenCalled();
                });

                it('updateTotalValue should calculate the price and update model and form fields', function () {
                    view.$el.find('[name=quantity]').val(5).trigger('input');
                    view.updateTotalValue({price: 100});
                    expect(view.$el.find('input[name=price]').val()).toEqual('500');
                    expect(view.$el.find('input[name=total_value]').val()).toEqual('500');
                    expect(model.get('total_value')).toEqual(500);
                });
            });


            describe('enrollment code', function () {
                beforeEach(function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                });

                it('should show the price field', function () {
                    expect(visible('[name=price]')).toBe(true);
                });

                it('should hide discount and code fields', function () {
                    expect(visible('[name=benefit_value]')).toBe(false);
                    expect(visible('[name=code]')).toBe(false);
                });

                it('should show the quantity field only for single-use vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(visible('[name=quantity]')).toBe(true);
                    view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(visible('[name=quantity]')).toBe(false);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(visible('[name=quantity]')).toBe(false);
                });
            });

            describe('discount code', function () {
                beforeEach(function () {
                    view.$el.find('[name=code_type]').val('Discount code').trigger('change');
                });

                it('should show the discount field', function () {
                    expect(visible('[name=benefit_value]')).toBe(true);
                });

                it('should indicate the benefit type', function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$el.find('.benefit-addon').html()).toBe('%');
                    view.$el.find('[name=benefit_type]').val('Absolute').trigger('change');
                    expect(view.$el.find('.benefit-addon').html()).toBe('$');
                });

                it('should toggle upper limit on the benefit value input', function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$el.find('[name="benefit_value"]').attr('max')).toBe('100');
                    view.$el.find('[name=benefit_type]').val('Absolute').trigger('change');
                    expect(view.$el.find('[name="benefit_value"]').attr('max')).toBe('');
                });

                it('should show the code field for once-per-customer and singe-use vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(visible('[name=code]')).toBe(true);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(visible('[name=code]')).toBe(true);
                });

                it('should show the usage number field only for once-per-customer vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(visible('[name=max_uses]')).toBe(false);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(visible('[name=max_uses]')).toBe(true);
                });

                it('should hide quantity field when code entered and single-use voucher selected', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    view.$el.find('[name=code]').val('E34T4GR342').trigger('input');
                    expect(visible('[name=quantity]')).toBe(false);
                    view.$el.find('[name=code]').val('').trigger('input');
                    expect(visible('[name=quantity]')).toBe(true);
                });

                it('should hide code field when quantity not 1 and single-use voucher selected', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    view.$el.find('[name=quantity]').val(21).trigger('change');
                    expect(visible('[name=code]')).toBe(false);
                    view.$el.find('[name=quantity]').val(1).trigger('change');
                    expect(visible('[name=code]')).toBe(true);
                });

                it('should show code field when changing to once-per-customer', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    view.$el.find('[name=quantity]').val(111).trigger('change');
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(visible('[name=code]')).toBe(true);
                });
            });

            describe('dynamic catalog coupon', function () {
                it('should update dynamic catalog view query with coupon catalog query', function() {
                    model.set('catalog_query', '*:*');
                    view.updateCatalogQuery();
                    expect(view.dynamic_catalog_view.query).toEqual(model.get('catalog_query'));
                });

                it('should update dynamic catalog view course seat types with coupon seat types', function() {
                    model.set('course_seat_types', ['verified']);
                    view.updateCourseSeatTypes();
                    expect(view.dynamic_catalog_view.seat_types).toEqual(model.get('course_seat_types'));
                });
            });

            describe('Invoice fields', function() {
                var prepaid_fields = [
                    '[name=invoice_number]',
                    '[name=invoiced_amount]',
                    '[name=invoice_payment_date]'
                ];

                it('should show prepaid invoice fields when "Already invoiced" is selected.', function() {
                    view.$el.find('#already_invoiced').prop('checked', true).trigger('change');
                    _.each(prepaid_fields, function(field) {
                        expect(visible(field)).toBe(true);
                    });
                    expect(visible('[name=invoice_discount_value]')).toBe(false);
                });
                it('should show postpaid invoice fields when "Invoiced after redemption" is selected.', function() {
                    view.$el.find('#invoice_after_redemption').prop('checked', true).trigger('change');
                    _.each(prepaid_fields, function(field) {
                        expect(visible(field)).toBe(false);
                    });
                    expect(visible('[name=invoice_discount_value]')).toBe(true);
                });
                it('should constrain discount value input to 100 for percentage.', function() {
                    view.$el.find('#invoice_after_redemption').prop('checked', true).trigger('change');
                    view.$el.find('#invoice_discount_percent').prop('checked', true).trigger('change');
                    expect(view.$el.find('[name=invoice_discount_value]').attr('max')).toBe('100');
                    view.$el.find('#invoice_discount_fixed').prop('checked', true).trigger('change');
                    expect(view.$el.find('[name=invoice_discount_value]').attr('max')).toBe('');
                });
                it('should display the appropriate icon for the discount value field.', function() {
                    view.$el.find('#invoice_after_redemption').prop('checked', true).trigger('change');
                    view.$el.find('#invoice_discount_percent').prop('checked', true).trigger('change');
                    expect(view.$el.find('.invoice-discount-addon').html()).toBe('%');
                    view.$el.find('#invoice_discount_fixed').prop('checked', true).trigger('change');
                    expect(view.$el.find('.invoice-discount-addon').html()).toBe('$');
                });
                it('should display tax deducted source field when TDS is selected.', function() {
                    view.$el.find('#tax_deducted').prop('checked', true).trigger('change');
                    expect(visible('[name=tax_deducted_source_value]')).toBe(true);
                    view.$el.find('#non_tax_deducted').prop('checked', true).trigger('change');
                    expect(visible('[name=tax_deducted_source_value]')).toBe(false);
                });
            });
        });
    }
);
