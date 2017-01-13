define([
        'jquery',
        'underscore',
        'views/coupon_form_view',
        'views/alert_view',
        'models/coupon_model',
        'test/mock_data/categories',
        'test/mock_data/coupons',
        'test/spec-utils',
        'ecommerce',
        'test/custom-matchers'
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
                    seatType = view.$('[name=seat_type]');
                    spyOn($, 'ajax').and.callFake(function (options) {
                        options.success(courseData);
                    });
                    view.$('[name=course_id]').val(courseId).trigger('input');
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

                it('should remove whitespace from email domains', function() {
                    view.$('[name=email_domains]').val('example1.com, example2.com').trigger('change');
                    expect(model.get('email_domains')).toEqual('example1.com,example2.com');
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
                    view.$('[name=code_type]').val('enrollment').trigger('change');
                });

                it('should show the price field', function () {
                    expect(SpecUtils.formGroup(view, '[name=price]')).toBeVisible();
                });

                it('should hide discount and code fields', function () {
                    expect(SpecUtils.formGroup(view, '[name=benefit_value]')).not.toBeVisible();
                    expect(SpecUtils.formGroup(view, '[name=code]')).not.toBeVisible();
                });
            });

            describe('toggle credit seats', function() {
                it('should hide non-credit seats and uncheck them.', function() {
                    view.$('#credit').prop('checked', true).trigger('change');
                    expect(view.$('input[id=verified], input[id=professional]').is(':checked')).toBe(false);
                    expect(view.$('.non-credit-seats')).not.toBeVisible();
                    expect(view.model.get('course_seat_types')[0]).toBe('credit');
                });

                it('should show non-credit seats.', function() {
                    view.$('#non-credit').prop('checked', true).trigger('change');
                    expect(view.$('.non-credit-seats')).toBeVisible();

                    view.$('input[id=verified]').prop('checked', true).trigger('change');
                    expect(view.model.get('course_seat_types')[0]).toBe('verified');
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
                    view.$('[name=code_type]').val('Discount code').trigger('change');
                });

                it('should show the discount field', function () {
                    expect(SpecUtils.formGroup(view, '[name=benefit_value]')).toBeVisible();
                });

                it('should indicate the benefit type', function () {
                    view.$('[name=code_type]').val('enrollment').trigger('change');
                    expect(view.$('.benefit-addon').html()).toBe('%');
                    view.$('[name=benefit_type]').val('Absolute').trigger('change');
                    expect(view.$('.benefit-addon').html()).toBe('$');
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
                    view.$('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).toBeVisible();
                    view.$('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).toBeVisible();
                });

                it('should show the max_uses field only for once-per-customer and multi-use vouchers', function () {
                    view.$('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=max_uses]')).not.toBeVisible();
                    view.$('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=max_uses]')).toBeVisible();
                    view.$('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=max_uses]')).toBeVisible();
                });

                it('should set different values for max_uses field for different voucher types', function () {
                    view.$('[name=voucher_type]').val('Single use').trigger('change');
                    expect(view.$('[name=max_uses]').val()).toBe('');
                    expect(view.$('[name=max_uses]').attr('min')).toBe('');
                    view.$('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(view.$('[name=max_uses]').val()).toBe('1');
                    expect(view.$('[name=max_uses]').attr('min')).toBe('1');
                    view.$('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(view.$('[name=max_uses]').val()).toBe('');
                    expect(view.$('[name=max_uses]').attr('min')).toBe('2');
                });

                it('should unset max_uses field for singe-use voucher', function () {
                    view.$('[name=voucher_type]').val('Single use').trigger('change');
                    expect(view.model.get('max_uses')).toBe(undefined);
                });

                it('should hide quantity field when code entered', function () {
                    view.$('[name=code]').val('E34T4GR342').trigger('input');
                    expect(SpecUtils.formGroup(view, '[name=quantity]')).not.toBeVisible();
                    view.$('[name=code]').val('').trigger('input');
                    expect(SpecUtils.formGroup(view, '[name=quantity]')).toBeVisible();
                });

                it('should hide code field when quantity not 1', function () {
                    view.$('[name=quantity]').val(21).trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).not.toBeVisible();
                    view.$('[name=quantity]').val(1).trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).toBeVisible();
                });

                it('should hide code field for every voucher type if quantity is not 1.', function() {
                    view.$('[name=quantity]').val(2).trigger('change');
                    view.$('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).not.toBeVisible();

                    view.$('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).not.toBeVisible();

                    view.$('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).not.toBeVisible();
                });

                it('should show the code field for every voucher type if quantity is 1.', function() {
                    view.$('[name=quantity]').val(1).trigger('change');
                    view.$('[name=voucher_type]').val('Single use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).toBeVisible();

                    view.$('[name=voucher_type]').val('Once per customer').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).toBeVisible();

                    view.$('[name=voucher_type]').val('Multi-use').trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=code]')).toBeVisible();
                });

                it('should show prepaid invoice fields when changing to Prepaid invoice type.', function() {
                    view.$('#already-invoiced').prop('checked', true).trigger('change');
                    _.each(prepaid_invoice_fields, function(field) {
                        expect(SpecUtils.formGroup(view, field)).toBeVisible();
                    });
                    expect(SpecUtils.formGroup(view, '[name=invoice_discount_value]')).not.toBeVisible();
                });

                it('should show postpaid invoice fields when changing to Postpaid invoice type.', function() {
                    view.$('#invoice-after-redemption').prop('checked', true).trigger('change');
                    _.each(prepaid_invoice_fields, function(field) {
                        expect(SpecUtils.formGroup(view, field)).not.toBeVisible();
                    });
                    expect(SpecUtils.formGroup(view, '[name=invoice_discount_value]')).toBeVisible();
                });

                it('should hide all invoice fields when changing to Not applicable invoice type.', function() {
                    view.$('#not-applicable').prop('checked', true).trigger('change');
                    _.each(prepaid_invoice_fields, function(field) {
                        expect(SpecUtils.formGroup(view, field)).not.toBeVisible();
                    });
                    expect(SpecUtils.formGroup(view, '[name=invoice_discount_value]')).not.toBeVisible();
                });

                it('should show tax deduction source field when TSD is selected.', function() {
                    view.$('#tax-deducted').prop('checked', true).trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=tax_deducted_source_value]')).toBeVisible();
                    view.$('#non-tax-deducted').prop('checked', true).trigger('change');
                    expect(SpecUtils.formGroup(view, '[name=tax_deducted_source_value]')).not.toBeVisible();
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

                it('should unset dynamic catalog values from fields when toggled to single course', function() {
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
                    expect(view.dynamic_catalog_view.seat_types).toEqual(undefined);
                });

                it('should update the query length indicator', function() {
                    var query_1 = 'example query',
                        query_2 = 'a larger example query';

                    view.$('textarea[name=catalog_query]').val(query_1).trigger('input');
                    expect(view.$('span.query_length').text()).toEqual(String(query_1.length));

                    view.$('textarea[name=catalog_query]').val(query_2).trigger('input');
                    expect(view.$('span.query_length').text()).toEqual(String(query_2.length));
                });

                it('should reset model fields to _initAttributes values when cancelButtonClicked called', function() {
                    view._initAttributes = {
                        'catalog_type': 'single',
                        'course_id': 'different from model course_id',
                        'course_seat_types': []
                    };
                    view.model.set({
                        'catalog_type': 'multy',
                        'catalog_query': 'query',
                        'course_seat_types': ['seat1','seat2']
                    });
                    view.cancelButtonClicked();
                    expect(view.model.get('catalog_type')).toEqual(view._initAttributes.catalog_type);
                    expect(view.model.get('catalog_query')).toEqual(view._initAttributes.catalog_query);
                    expect(view.model.get('course_seat_types')).toEqual(view._initAttributes.course_seat_types);
                });

                it('should unset all single course attributes when multiple courses selected', function () {
                    view.model.set({
                        'course_id': 'course id',
                        'seat_type': 'seat type',
                        'stock_record_ids': [1]
                    });
                    view.$('#multiple-courses').prop('checked', true).trigger('change');
                    expect(view.model.get('course_id')).toEqual(undefined);
                    expect(view.model.get('seat_type')).toEqual(undefined);
                    expect(view.model.get('stock_record_ids')).toEqual(undefined);
                });
            });
        });
    }
);
