define([
    'jquery',
    'underscore.string',
    'utils/utils',
    'views/coupon_create_edit_view',
    'models/coupon_model',
    'test/mock_data/coupons',
    'test/mock_data/catalogs',
    'test/mock_data/enterprise_customers',
    'test/spec-utils'
],
    function($,
              _s,
              Utils,
              CouponCreateEditView,
              Coupon,
              MockCoupons,
              MockCatalogs,
              MockCustomers,
              SpecUtils) {
        'use strict';

        describe('coupons edit view', function() {
            var view,
                model,
                enrollmentCodeData = MockCoupons.enrollmentCodeCouponData,
                discountCodeData = MockCoupons.discountCodeCouponData,
                invoiceCouponData = MockCoupons.couponWithInvoiceData,
                dynamicCoupon = MockCoupons.dynamicCouponData,
                multiUseCouponData = MockCoupons.enrollmentMultiUseCouponData;

            describe('edit enrollment code', function() {
                beforeEach(function() {
                    enrollmentCodeData.course_catalog = MockCatalogs;
                    enrollmentCodeData.enterprise_customer = MockCustomers[0];
                    model = Coupon.findOrCreate(enrollmentCodeData, {parse: true});
                    model.updateSeatData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display coupon details in form fields', function() {
                    var voucherType = view.$el.find('[name=voucher_type]'),
                        startDate = Utils.stripTimezone(model.get('start_date')),
                        endDate = Utils.stripTimezone(model.get('end_date'));
                    expect(view.$el.find('[name=title]').val()).toEqual(model.get('title'));
                    expect(view.$el.find('[name=code_type]').val()).toEqual('Enrollment code');
                    expect(view.$el.find('[name=start_date]').val()).toEqual(startDate);
                    expect(view.$el.find('[name=end_date]').val()).toEqual(endDate);
                    expect(voucherType.children().length).toBe(3);
                    expect(voucherType.val()).toEqual(model.get('voucher_type'));
                    expect(view.$el.find('[name=quantity]').val()).toEqual(model.get('quantity').toString());
                    expect(view.$el.find('[name=client]').val()).toEqual(model.get('client'));
                    expect(view.$el.find('[name=price]').val()).toEqual(model.get('price'));
                    expect(view.$el.find('[name=course_id]').val()).toEqual(model.get('course_id'));
                    expect(view.$el.find('[name=enterprise_customer]').val()).toEqual(
                        model.get('enterprise_customer').id
                    );
                });

                it('should verify single-use voucher max_uses field min attribute is empty string', function() {
                    expect(view.$('[name=max_uses]').attr('min')).toBe('');
                });
            });

            describe('edit discount code', function() {
                beforeEach(function() {
                    model = new Coupon(discountCodeData);
                    model.updateSeatData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                afterEach(function() {
                    model.destroy();
                });

                it('should display coupon details in form fields', function() {
                    var voucherType = view.$el.find('[name=voucher_type]'),
                        startDate = Utils.stripTimezone(model.get('start_date')),
                        endDate = Utils.stripTimezone(model.get('end_date'));
                    expect(view.$el.find('[name=title]').val()).toEqual(model.get('title'));
                    expect(view.$el.find('[name=code_type]').val()).toEqual('Discount code');
                    expect(view.$el.find('[name=start_date]').val()).toEqual(startDate);
                    expect(view.$el.find('[name=end_date]').val()).toEqual(endDate);
                    expect(voucherType.children().length).toBe(3);
                    expect(voucherType.val()).toEqual(model.get('voucher_type'));
                    expect(view.$el.find('[name=quantity]').val()).toEqual(model.get('quantity').toString());
                    expect(view.$el.find('[name=client]').val()).toEqual(model.get('client'));
                    expect(view.$el.find('[name=price]').val()).toEqual(model.get('price'));
                    expect(view.$el.find('[name=course_id]').val()).toEqual(model.get('course_id'));
                    expect(view.$el.find('[name=benefit_type]').val()).toEqual(model.get('benefit_type'));
                    expect(view.$el.find('[name=benefit_value]').val()).toEqual(model.get('benefit_value').toString());
                    expect(view.$el.find('[name=code]').val()).toEqual(model.get('code'));
                });

                it('should hide code field when quantity is greater than one', function() {
                    view.model.set('quantity', 2);
                    view.render();
                    expect(SpecUtils.formGroup(view, '[name=code]')).toHaveHiddenClass();
                    expect(SpecUtils.formGroup(view, '[name=quantity]')).not.toHaveHiddenClass();
                });

                it('should hide quantity field when code is set', function() {
                    view.model.set('code', 'RANDOMCODE');
                    view.render();
                    expect(SpecUtils.formGroup(view, '[name=code]')).not.toHaveHiddenClass();
                    expect(SpecUtils.formGroup(view, '[name=quantity]')).toHaveHiddenClass();
                });
            });

            describe('Editing dynamic coupon', function() {
                beforeEach(function() {
                    model = Coupon.findOrCreate(dynamicCoupon);
                    model.updateSeatData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display dynamic catalog information.', function() {
                    expect(view.$('#catalog-query').val()).toEqual(model.get('catalog_query'));
                    expect(view.$('#non-credit, #verified, #professional').is(':checked')).toEqual(true);
                });

                it('should hide checkboxes if credit seat type.', function() {
                    var creditSeatType = ['credit'];
                    model.set('course_seat_types', creditSeatType);
                    view.render();
                    expect(view.$('.non-credit-seats')).toHaveHiddenClass();
                });
            });

            describe('Coupon with invoice data', function() {
                beforeEach(function() {
                    model = Coupon.findOrCreate(invoiceCouponData, {parse: true});
                    model.updatePaymentInformation();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should contain invoice attributes.', function() {
                    var tds,
                        paymentDate = Utils.stripTimezone(model.get('invoice_payment_date'));
                    if (model.get('tax_deducted_source')) {
                        tds = 'Yes';
                    } else {
                        tds = 'No';
                    }
                    expect(view.$el.find('[name=invoice_type]').val()).toEqual(model.get('invoice_type'));
                    expect(view.$el.find('[name=invoice_number]').val()).toEqual(model.get('invoice_number'));
                    expect(view.$el.find('[name=invoice_discount_value]').val()).toEqual('');
                    expect(view.$el.find('[name=invoice_payment_date]').val()).toEqual(paymentDate);
                    expect(view.$el.find('[name=tax_deduction]:checked').val()).toEqual(tds);
                    expect(view.$el.find('[name=tax_deducted_source_value]').val())
                        .toEqual(model.get('tax_deducted_source'));
                });

                it('should patch save the model when form is in editing mode and has editable attributes', function() {
                    var formView = view.formView;
                    spyOn(formView.model, 'save');
                    spyOn(formView.model, 'isValid').and.returnValue(true);

                    expect(formView.modelServerState).toEqual(model.pick(formView.editableAttributes));
                    formView.model.set('title', 'Test Title');
                    formView.submit($.Event('click'));
                    expect(model.save).toHaveBeenCalled();
                });
            });

            describe('Editing multi-use single course enrollment coupon', function() {
                beforeEach(function() {
                    model = Coupon.findOrCreate(multiUseCouponData, {parse: true});
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display model max_uses value in max_uses field.', function() {
                    expect(view.$('[name=max_uses]').val()).toEqual(model.get('max_uses'));
                    expect(view.$('[name=voucher_type]').val()).toEqual(model.get('voucher_type'));
                });

                it('should reset catalog related values to initial values when cancel button pressed', function() {
                    var formView = view.formView;
                    view.$('#multiple-courses').prop('checked', true).trigger('change');
                    /* eslint-disable no-underscore-dangle */
                    expect(view.model.get('catalog_type')).not.toBe(formView._initAttributes.catalog_type);
                    expect(view.model.get('course_id')).not.toBe(formView._initAttributes.course_id);
                    expect(view.model.get('seat_type')).not.toBe(formView._initAttributes.seat_type);
                    view.$('#cancel-button').click();
                    expect(view.model.get('catalog_type')).toBe(formView._initAttributes.catalog_type);
                    expect(view.model.get('course_id')).toBe(formView._initAttributes.course_id);
                    expect(view.model.get('seat_type')).toBe(formView._initAttributes.seat_type);
                    /* eslint-enable no-underscore-dangle */
                });

                it('should not update price when editing coupon', function() {
                    var formView = view.formView;
                    spyOn(formView, 'updateTotalValue');
                    formView.changeSeatType();
                    expect(formView.updateTotalValue).not.toHaveBeenCalled();
                });

                it('should verify multi-use max_uses field min attribute is set to num_uses.', function() {
                    expect(view.$('[name=max_uses]').attr('min')).toBe(view.model.get('num_uses'));
                });

                it('should verify once-per-customer max_uses field min attribute is set to num_uses', function() {
                    view.model.set('voucher_type', 'Once per customer');
                    view.render();
                    expect(view.$('[name=max_uses]').attr('min')).toBe(view.model.get('num_uses'));
                });
            });
        });
    }
);
