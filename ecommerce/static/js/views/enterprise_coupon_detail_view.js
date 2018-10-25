define([
    'jquery',
    'backbone',
    'ecommerce',
    'underscore',
    'underscore.string',
    'moment',
    'text!templates/_alert_div.html',
    'text!templates/enterprise_coupon_detail.html',
    'utils/alert_utils'
],
    function($,
              Backbone,
              ecommerce,
              _,
              _s,
              moment,
              AlertDivTemplate,
              CouponDetailTemplate,
              AlertUtils) {
        'use strict';

        return Backbone.View.extend({
            className: 'coupon-detail-view',

            events: {
                'click .voucher-report-button': 'downloadCouponReport'
            },

            template: _.template(CouponDetailTemplate),

            initialize: function() {
                this.alertViews = [];
            },

            formatDateTime: function(dateTime) {
                return moment.utc(dateTime).format('MM/DD/YYYY h:mm A');
            },

            formatLastEditedData: function(lastEdited) {
                return _s.sprintf('%s - %s', lastEdited[0], this.formatDateTime(lastEdited[1]));
            },

            discountValue: function() {
                var stringFormat = (this.model.get('benefit_type') === 'Percentage') ? '%u%%' : '$%u';
                return _s.sprintf(stringFormat, this.model.get('benefit_value'));
            },

            taxDeductedSource: function(value) {
                if (value) {
                    return _s.sprintf('%u%%', parseInt(value, 10));
                } else {
                    return null;
                }
            },

            invoiceDiscountValue: function(type, value) {
                var stringFormat = (type === 'Percentage') ? '%u%%' : '$%u';
                return _s.sprintf(stringFormat, parseInt(value, 10));
            },

            formatInvoiceData: function() {
                var invoicePaymentDate = this.model.get('invoice_payment_date'),
                    invoiceDiscountType = this.model.get('invoice_discount_type'),
                    invoiceDiscountValue = this.model.get('invoice_discount_value'),
                    taxDeductedSource = this.model.get('tax_deducted_source');

                if (invoiceDiscountValue === null) {
                    invoiceDiscountType = null;
                } else {
                    invoiceDiscountValue = this.invoiceDiscountValue(invoiceDiscountType, invoiceDiscountValue);
                }
                taxDeductedSource = this.taxDeductedSource(taxDeductedSource);

                if (invoicePaymentDate) {
                    invoicePaymentDate = this.formatDateTime(invoicePaymentDate);
                }
                return {
                    invoice_type: this.model.get('invoice_type'),
                    invoice_number: this.model.get('invoice_number'),
                    invoice_payment_date: invoicePaymentDate,
                    invoice_discount_type: invoiceDiscountType,
                    invoice_discount_value: invoiceDiscountValue,
                    invoiced_amount: this.model.get('invoiced_amount'),
                    tax_deducted_source_value: taxDeductedSource
                };
            },

            usageLimitation: function() {
                var voucherType = this.model.get('voucher_type');
                if (voucherType === 'Single use') {
                    return gettext('Can be used once by one customer');
                } else if (voucherType === 'Multi-use') {
                    return gettext('Can be used multiple times by multiple customers');
                } else if (voucherType === 'Once per customer') {
                    return gettext('Can be used once by multiple customers');
                }
                return '';
            },

            render: function() {
                var html,
                    category = this.model.get('category').name,
                    invoiceData = this.formatInvoiceData(),
                    emailDomains = this.model.get('email_domains'),
                    lastEdited = this.model.get('last_edited'),
                    templateData,
                    price = null;

                if (this.model.get('price') !== '0.00') {
                    price = _s.sprintf('$%s', this.model.get('price'));
                }

                templateData = {
                    category: category,
                    coupon: this.model.toJSON(),
                    discountValue: this.discountValue(),
                    endDateTime: this.formatDateTime(this.model.get('end_date')),
                    lastEdited: lastEdited ? this.formatLastEditedData(lastEdited) : '',
                    price: price,
                    startDateTime: this.formatDateTime(this.model.get('start_date')),
                    usage: this.usageLimitation(),
                    emailDomains: emailDomains
                };

                $.extend(templateData, invoiceData);
                html = this.template(templateData);

                this.$el.html(html);
                this.delegateEvents();

                this.$('.coupon-information').before(AlertDivTemplate);
                this.$alerts = this.$el.find('.alerts');

                return this;
            },

            downloadCouponReport: function(event) {
                var url = _s.sprintf('/api/v2/coupons/coupon_reports/%d', this.model.id),
                    self = this;

                $.ajax({
                    url: url,
                    type: 'GET',
                    success: function() {
                        event.preventDefault();
                        window.open(url, '_blank');
                        return self;
                    },
                    error: function(data) {
                        AlertUtils.clearAlerts(self);
                        AlertUtils.renderAlert('danger', '', data.responseText, self);
                    }
                });
            }
        });
    }
);
