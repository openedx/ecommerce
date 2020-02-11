define([
    'jquery',
    'underscore.string',
    'models/enterprise_coupon_model',
    'utils/alert_utils',
    'ecommerce',
    'collections/catalog_collection',
    'views/enterprise_coupon_detail_view',
    'test/mock_data/coupons',
    'test/custom-matchers'
],
    function($,
              _s,
              EnterpriseCoupon,
              AlertUtils,
              ecommerce,
              CatalogCollection,
              EnterpriseCouponDetailView,
              MockCoupons) {
        'use strict';

        describe('coupon detail view', function() {
            var data,
                model,
                view;

            beforeEach(function() {
                data = MockCoupons.enterpriseCouponData;
                model = EnterpriseCoupon.findOrCreate(data, {parse: true});
                view = new EnterpriseCouponDetailView({model: model});
            });

            it('should compare view.model with model sent', function() {
                expect(view.model).toBe(model);
            });

            it('should display correct data upon rendering', function() {
                var category = model.get('category').name;

                view.render();
                expect(view.$('.coupon-title').text()).toEqual(model.get('title'));
                expect(view.$('.coupon-type').text()).toEqual(model.get('coupon_type'));
                expect(view.$('.code-status').text()).toEqual(model.get('code_status'));
                expect(view.$('.category > .value').text()).toEqual(category);
                expect(view.$('.discount-value > .value').text()).toEqual(view.discountValue());
                expect(view.$('.enterprise-customer > .value').text()).toEqual(
                    model.get('enterprise_customer').id
                );
                expect(
                    view.$('.enterprise-customer-catalog > .value > .enterprise-catalog-details-link').text()
                ).toEqual(
                    model.get('enterprise_customer_catalog')
                );
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
