define([
    'jquery',
    'underscore.string',
    'models/coupon_model',
    'utils/alert_utils',
    'ecommerce',
    'collections/catalog_collection',
    'views/coupon_detail_view',
    'test/mock_data/coupons',
    'test/spec-utils',
    'test/custom-matchers'
],
    function($,
              _s,
              Coupon,
              AlertUtils,
              ecommerce,
              CatalogCollection,
              CouponDetailView,
              MockCoupons,
              SpecUtils) {
        'use strict';

        describe('coupon detail view', function() {
            var data,
                lastEditData,
                model,
                view;

            beforeEach(function() {
                data = MockCoupons.enrollmentCodeCouponData;
                model = Coupon.findOrCreate(data, {parse: true});
                view = new CouponDetailView({model: model});
                lastEditData = MockCoupons.lastEditData;
            });

            afterEach(function() {
                // Unset all attributes that could disrupt other tests
                view.model.unset('catalog_query');
                view.model.unset('course_seat_types');
            });

            it('should compare view.model with model sent', function() {
                expect(view.model).toBe(model);
            });

            it('should get discount value from voucher data', function() {
                expect(view.discountValue()).toBe('100%');
                view.model.set({benefit_type: 'Absolute', benefit_value: 12.0});
                expect(view.discountValue()).toBe('$12');
            });

            it('should get usage limitation from voucher data', function() {
                expect(view.usageLimitation()).toBe('Can be used once by one customer');

                view.model.set('voucher_type', 'Once per customer');
                expect(view.usageLimitation()).toBe('Can be used once by multiple customers');

                view.model.set('voucher_type', 'Multi-use');
                expect(view.usageLimitation()).toBe('Can be used multiple times by multiple customers');

                view.model.set('voucher_type', '');
                expect(view.usageLimitation()).toBe('');
            });

            it('should format date time as MM/DD/YYYY h:mm A', function() {
                expect(view.formatDateTime('2015-01-01T00:00:00Z')).toBe('01/01/2015 12:00 AM');
            });

            it('should format last edit data', function() {
                expect(view.formatLastEditedData(lastEditData)).toBe('user - 01/15/2016 7:26 AM');
            });

            it('should format tax deducted source value.', function() {
                expect(view.taxDeductedSource(50)).toBe('50%');
                expect(view.taxDeductedSource()).toBe(null);
            });

            it('should display correct data upon rendering', function() {
                var category = model.get('category').name;

                view.render();
                expect(view.$('.coupon-title').text()).toEqual(model.get('title'));
                expect(view.$('.coupon-type').text()).toEqual(model.get('coupon_type'));
                expect(view.$('.code-status').text()).toEqual(model.get('code_status'));
                expect(view.$('.coupon-information > .heading > .pull-right > span').text()).toEqual(
                    view.formatLastEditedData(model.get('last_edited'))
                );
                expect(view.$('.category > .value').text()).toEqual(category);
                expect(view.$('.discount-value > .value').text()).toEqual(view.discountValue());
                expect(view.$('.course-info > .value').contents().get(0).nodeValue).toEqual(
                    'course-v1:edX+DemoX+Demo_Course'
                );
                expect(view.$('.course-info > .value > .pull-right').text()).toEqual('verified');
                expect(view.$('.start-date-info > .value').text()).toEqual(
                    view.formatDateTime(model.get('start_date'))
                );
                expect(view.$('.end-date-info > .value').text()).toEqual(
                    view.formatDateTime(model.get('end_date'))
                );
                expect(view.$('.usage-limitations > .value').text()).toEqual(view.usageLimitation());
                expect(view.$('.client-info > .value').text()).toEqual(model.get('client'));
                expect(view.$('.invoiced-amount > .value').text()).toEqual(
                    _s.sprintf('$%s', model.get('price'))
                );
                expect(parseInt(view.$('.max-uses > .value').text(), 10)).toEqual(parseInt(model.get('max_uses'), 10));
                expect(view.$('.invoice-type > .value').text()).toEqual(model.get('invoice_type'));
                expect(view.$('.invoice-number > .value').text()).toEqual(model.get('invoice_number'));
                expect(view.$('.invoice-payment-date > .value').text()).toEqual(
                    view.formatDateTime(model.get('invoice_payment_date'))
                );
                expect(view.$('.invoice-discount-value > .value').text()).toEqual(
                    view.invoiceDiscountValue(
                        model.get('invoice_discount_type'),
                        model.get('invoice_discount_value')
                    )
                );
                expect(view.$('.tax-deducted-source-value > .value').text()).toEqual(
                    view.taxDeductedSource(model.get('tax_deducted_source'))
                );
                expect(view.$('.seat-types > .value').text()).toEqual('');
                expect(view.$('.catalog-query > .value').text()).toEqual('');
            });

            it('should not display invoice discount type on render.', function() {
                data = MockCoupons.enrollmentCodeCouponData;
                data.invoice_discount_value = null;
                model = Coupon.findOrCreate(data, {parse: true});
                view = new CouponDetailView({model: model});
                view.render();
                expect(view.$('.invoice-discount-value > .value').text()).toEqual('');
                expect(view.$('.invoice-discount-type > .value').text()).toEqual('');
            });

            it('should display course catalog name and course seats without preview button on render.', function() {
                ecommerce.coupons.catalogs = new CatalogCollection([{id: 1, name: 'Test Catalog'}]);

                data.course_catalog = 1;
                data.course_seat_types = ['verified'];
                model = Coupon.findOrCreate(data, {parse: true, create: true});
                view = new CouponDetailView({model: model});
                view.render();

                expect(view.$('.catalog-name > .value').text()).toEqual('Test Catalog');
                expect(view.$('.seat-types .value').text()).toEqual(
                     data.course_seat_types.join(', ')
                 );
                expect(view.$('.catalog_buttons').text()).toEqual('');
            });

            it('should format seat types.', function() {
                view.model.unset('course_seat_types');
                expect(view.formatSeatTypes()).toEqual(null);

                view.model.set({course_seat_types: ['verified']});
                expect(view.formatSeatTypes()).toEqual('verified');

                view.model.set({course_seat_types: ['verified', 'professional']});
                expect(view.formatSeatTypes()).toEqual('verified, professional');
            });

            it('should render course data', function() {
                var courseInfo;
                view.model.set({
                    catalog_type: 'Single course',
                    course_id: 'a/b/c',
                    seat_type: 'Verified',
                    course_seat_types: ['verified']
                });

                view.render();

                courseInfo = view.$('.course-info .value');
                expect(courseInfo.length).toEqual(1);
                expect(courseInfo.text()).toEqual('a/b/cVerified');
                expect(view.$('.seat-types .value').text()).toEqual('verified');

                view.model.set({
                    catalog_type: 'Multiple courses',
                    catalog_query: 'id:*',
                    course_seat_types: ['verified', 'professional']
                });

                view.render();

                expect(view.$('.catalog-query .value').text()).toEqual('id:*');
                expect(view.$('.seat-types .value').text()).toEqual('verified, professional');
            });

            it('should render prepaid invoice data.', function() {
                view.model.set({
                    invoice_type: 'Prepaid',
                    invoice_number: 'INV-001',
                    price: 1000,
                    invoice_payment_date: new Date(2016, 1, 1, 1, 0, 0)
                });
                view.render();

                expect(view.$('.invoice-number .value').text()).toEqual(model.get('invoice_number'));
                expect(view.$('.invoiced-amount .value').text()).toEqual(
                    _s.sprintf('$%s', model.get('price'))
                );
                expect(view.$('.invoice-payment-date .value').text()).toEqual(
                    view.formatDateTime(model.get('invoice_payment_date'))
                );
                expect(view.$('.invoice_discount_type')).not.toBeVisible();
                expect(view.$('.invoice_discount_value')).not.toBeVisible();
            });

            it('should render postpaid invoice data.', function() {
                view.model.set({
                    invoice_type: 'Postpaid',
                    invoice_discount_type: 'Percentage',
                    invoice_discount_value: 50
                });
                view.render();
                expect(view.$('.invoice-discount-value .value').text()).toEqual(
                    view.invoiceDiscountValue(
                        model.get('invoice_discount_type'),
                        model.get('invoice_discount_value')
                    )
                );
                expect(SpecUtils.formGroup(view, '.invoice-number')).not.toBeVisible();
                expect(SpecUtils.formGroup(view, '.invoiced-amount')).not.toBeVisible();
                expect(SpecUtils.formGroup(view, '.invoice-payment-date')).not.toBeVisible();
            });

            it('should render not-applicable invoice data.', function() {
                view.model.set('invoice_type', 'Not-Applicable');
                view.render();
                expect(SpecUtils.formGroup(view, '.invoice_discount_type')).not.toBeVisible();
                expect(SpecUtils.formGroup(view, '.invoice-number')).not.toBeVisible();
                expect(SpecUtils.formGroup(view, '.invoiced-amount')).not.toBeVisible();
                expect(SpecUtils.formGroup(view, '.invoice-payment-date')).not.toBeVisible();
            });

            it('should display tax deducted source input field.', function() {
                view.model.set('tax_deduction', 'Yes');
                view.render();
                expect(view.$('.tax-deducted-source-value').closest('.info-item')).not.toHaveHiddenClass();
                view.model.set('tax_deduction', 'No');
                view.render();
                expect(SpecUtils.formGroup(view, '.tax-deducted-source-value')).not.toBeVisible();
            });

            it('should download voucher report in the new tab', function() {
                var e = $.Event('click'),
                    url = _s.sprintf('/api/v2/coupons/coupon_reports/%d', model.id);
                spyOn($, 'ajax').and.callFake(function(options) {
                    options.success();
                });
                spyOn(e, 'preventDefault');
                spyOn(window, 'open');
                view.downloadCouponReport(e);
                expect(e.preventDefault).toHaveBeenCalled();
                expect(window.open).toHaveBeenCalledWith(url, '_blank');
            });

            it('should display error when download voucher fails', function() {
                var e = $.Event('click');
                spyOn($, 'ajax').and.callFake(function(options) {
                    options.error(data);
                });
                spyOn(AlertUtils, 'clearAlerts');
                spyOn(AlertUtils, 'renderAlert');
                view.downloadCouponReport(e);
                expect(AlertUtils.clearAlerts).toHaveBeenCalled();
                expect(AlertUtils.renderAlert).toHaveBeenCalled();
            });
        });
    }
);
