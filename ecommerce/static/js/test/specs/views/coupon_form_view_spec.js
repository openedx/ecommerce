define([
        'jquery',
        'underscore',
        'views/coupon_form_view',
        'views/alert_view',
        'models/coupon_model',
        'test/mock_data/categories',
        'test/mock_data/coupons',
        'test/spec-utils',
        'ecommerce'
    ],
    function ($,
              _,
              CouponFormView,
              AlertView,
              Coupon,
              Mock_Categories,
              Mock_Coupons,
              SpecUtils,
              ecommerce) {
        'use strict';

        describe('coupon form view', function () {
            var view,
                model,
                courseData = Mock_Coupons.courseData;

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
            });

            describe('enrollment code', function () {
                beforeEach(function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                });

                it('should show the price field', function () {
                    expect(SpecUtils.visibleElement(view, '[name=price]', '.form-group')).toBe(true);
                });

                it('should hide discount and code fields', function () {
                    expect(SpecUtils.visibleElement(view, '[name=benefit_value]', '.form-group')).toBe(false);
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(false);
                });
            });

            describe('routing', function() {
                it('should route to external link.', function() {
                    var href = 'http://www.google.com/';
                    spyOn(window, 'open');
                    view.$el.append('<a href="' + href + '" class="test external-link">Google</a>');
                    view.$('.test.external-link').click();
                    expect(window.open).toHaveBeenCalledWith(href);
                });
            });

            describe('discount code', function () {
                var prepaid_invoice_fields = [
                    '[name=invoice_number]',
                    '[name=price]',
                    '[name=invoice_payment_date]'
                ];

                beforeEach(function () {
                    view.$el.find('[name=code_type]').val('Discount code').trigger('change');
                });

                it('should show the discount field', function () {
                    expect(SpecUtils.visibleElement(view, '[name=benefit_value]', '.form-group')).toBe(true);
                });

                it('should indicate the benefit type', function () {
                    view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$el.find('.benefit-addon').html()).toBe('%');
                    view.$el.find('[name=benefit_type]').val('Absolute').trigger('change');
                    expect(view.$el.find('.benefit-addon').html()).toBe('$');
                });

                it('should toggle limit on the benefit value input', function () {
                    view.$('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$('[name="benefit_value"]').attr('max')).toBe('');
                    expect(view.$('[name="benefit_value"]').attr('min')).toBe('');

                    view.$('[name=code_type]').val('Discount code').trigger('change');
                    expect(view.$('[name="benefit_value"]').attr('max')).toBe('100');
                    expect(view.$('[name="benefit_value"]').attr('min')).toBe('1');

                    view.$('[name=benefit_type]').val('Absolute').trigger('change');
                    expect(view.$('[name="benefit_value"]').attr('max')).toBe('');
                    expect(view.$('[name="benefit_value"]').attr('min')).toBe('1');
                });

                it('should toggle limit on the invoice discount value input', function () {
                    view.$('#invoice-discount-percent').prop('checked', true).trigger('change');
                    expect(view.$('[name="invoice_discount_value"]').attr('max')).toBe('100');
                    expect(view.$('[name="invoice_discount_value"]').attr('min')).toBe('1');

                    view.$('#invoice-discount-fixed').prop('checked', true).trigger('change');
                    expect(view.$('[name="invoice_discount_value"]').attr('max')).toBe('');
                    expect(view.$('[name="invoice_discount_value"]').attr('min')).toBe('1');
                });

                it('should show the code field for once-per-customer and singe-use vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(true);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(true);
                });

                it('should show the usage number field only for once-per-customer vouchers', function () {
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=max_uses]', '.form-group')).toBe(false);
                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=max_uses]', '.form-group')).toBe(true);
                });

                it('should hide quantity field when code entered', function () {
                    view.$el.find('[name=code]').val('E34T4GR342').trigger('input');
                    expect(SpecUtils.visibleElement(view, '[name=quantity]', '.form-group')).toBe(false);
                    view.$el.find('[name=code]').val('').trigger('input');
                    expect(SpecUtils.visibleElement(view, '[name=quantity]', '.form-group')).toBe(true);
                });

                it('should hide code field when quantity not 1', function () {
                    view.$el.find('[name=quantity]').val(21).trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(false);
                    view.$el.find('[name=quantity]').val(1).trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(true);
                });

                it('should hide code field for every voucher type if quantity is not 1.', function() {
                    view.$el.find('[name=quantity]').val(2).trigger('change');
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(false);

                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(false);

                    view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(false);
                });

                it('should show the code field for every voucher type if quantity is 1.', function() {
                    view.$el.find('[name=quantity]').val(1).trigger('change');
                    view.$el.find('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(true);

                    view.$el.find('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(true);

                    view.$el.find('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(SpecUtils.visibleElement(view, '[name=code]', '.form-group')).toBe(true);
                });

                it('should show prepaid invoice fields when changing to Prepaid invoice type.', function() {
                    view.$el.find('#already-invoiced').prop('checked', true).trigger('change');
                    _.each(prepaid_invoice_fields, function(field) {
                        expect(SpecUtils.visibleElement(view, field, '.form-group')).toBe(true);
                    });
                    expect(SpecUtils.visibleElement(view, '[name=invoice_discount_value]', '.form-group')).toBe(false);
                });

                it('should show postpaid invoice fields when changing to Postpaid invoice type.', function() {
                    view.$el.find('#invoice-after-redemption').prop('checked', true).trigger('change');
                    _.each(prepaid_invoice_fields, function(field) {
                        expect(SpecUtils.visibleElement(view, field, '.form-group')).toBe(false);
                    });
                    expect(SpecUtils.visibleElement(view, '[name=invoice_discount_value]', '.form-group')).toBe(true);
                });

                it('should hide all invoice fields when changing to Not applicable invoice type.', function() {
                    view.$el.find('#not-applicable').prop('checked', true).trigger('change');
                    _.each(prepaid_invoice_fields, function(field) {
                        expect(SpecUtils.visibleElement(view, field, '.form-group')).toBe(false);
                    });
                    expect(SpecUtils.visibleElement(view, '[name=invoice_discount_value]', '.form-group')).toBe(false);
                });

                it('should show tax deduction source field when TSD is selected.', function() {
                    view.$el.find('#tax-deducted').prop('checked', true).trigger('change');
                    expect(
                        SpecUtils.visibleElement(view, '[name=tax_deducted_source_value]', '.form-group')
                    ).toBe(true);
                    view.$el.find('#non-tax-deducted').prop('checked', true).trigger('change');
                    expect(
                        SpecUtils.visibleElement(view, '[name=tax_deducted_source_value]', '.form-group')
                    ).toBe(false);
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

                it('should remove dynamic catalog values from fields when toggled to single course', function() {
                    var catalog_query = '*:*',
                        course_seat_types = ['verified'];

                    model.set('catalog_query', catalog_query);
                    model.set('course_seat_types', course_seat_types);
                    view.updateCatalogQuery();
                    view.updateCourseSeatTypes();
                    expect(view.dynamic_catalog_view.query).toEqual(catalog_query);
                    expect(view.dynamic_catalog_view.seat_types).toEqual(course_seat_types);

                    view.$('#single-course').prop('checked', true);
                    view.toggleCatalogTypeField();
                    expect(view.dynamic_catalog_view.query).toEqual(undefined);
                    expect(view.dynamic_catalog_view.seat_types).toEqual([ ]);
                });
            });
        });
    }
);
