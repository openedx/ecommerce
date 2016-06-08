define([
        'underscore.string',
        'utils/utils',
        'views/coupon_create_edit_view',
        'models/coupon_model',
        'test/mock_data/coupons',

    ],
    function (_s,
              Utils,
              CouponCreateEditView,
              Coupon,
              Mock_Coupons) {

        'use strict';

        describe('coupons edit view', function () {
            var view,
                model,
                enrollment_code_data = Mock_Coupons.enrollmentCodeCouponData,
                discount_code_data = Mock_Coupons.discountCodeCouponData,
                invoice_coupon_data = Mock_Coupons.couponWithInvoiceData;


            describe('edit enrollment code', function () {
                beforeEach(function () {
                    model = Coupon.findOrCreate(enrollment_code_data, {parse: true});
                    model.updateSeatData();
                    model.updateVoucherData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display coupon details in form fields', function () {
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
                });
            });

            describe('edit discount code', function () {
                beforeEach(function () {
                    model = new Coupon(discount_code_data);
                    model.updateSeatData();
                    model.updateVoucherData();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should display coupon details in form fields', function () {
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
            });

            describe('Coupon with invoice data', function() {
                beforeEach(function() {
                    model = Coupon.findOrCreate(invoice_coupon_data, {parse: true});
                    model.updatePaymentInformation();
                    view = new CouponCreateEditView({model: model, editing: true}).render();
                });

                it('should contain invoice attributes.', function() {
                    var tds, payment_date = Utils.stripTimezone(model.get('invoice_payment_date'));
                    if (model.get('tax_deducted_source')) {
                        tds = 'Yes';
                    } else {
                        tds = 'No';
                    }
                    expect(view.$el.find('[name=invoice_type]').val()).toEqual(model.get('invoice_type'));
                    expect(view.$el.find('[name=invoice_number]').val()).toEqual(model.get('invoice_number'));
                    expect(view.$el.find('[name=invoice_discount_value]').val()).toEqual('');
                    expect(view.$el.find('[name=invoiced_amount]').val()).toEqual(model.get('invoiced_amount'));
                    expect(view.$el.find('[name=invoice_payment_date]').val()).toEqual(payment_date);
                    expect(view.$el.find('[name=tax_deducted_source]:checked').val()).toEqual(tds);
                    expect(view.$el.find('[name=tax_deducted_source_value]').val())
                        .toEqual(model.get('tax_deducted_source_value'));
                });
            });
        });
    }
);
