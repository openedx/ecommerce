define([
    'jquery',
    'backbone',
    'ecommerce',
    'underscore',
    'underscore.string',
    'moment',
    'text!templates/_alert_div.html',
    'text!templates/coupon_detail.html',
    'utils/alert_utils',
    'views/dynamic_catalog_view'
],
    function($,
              Backbone,
              ecommerce,
              _,
              _s,
              moment,
              AlertDivTemplate,
              CouponDetailTemplate,
              AlertUtils,
              DynamicCatalogView) {
        'use strict';

        return Backbone.View.extend({
            className: 'coupon-detail-view',

            events: {
                'click .voucher-report-button': 'downloadCouponReport',
                'click .external-link': 'routeToLink'
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

            formatSeatTypes: function() {
                var courseSeatTypes = this.model.get('course_seat_types');
                if (courseSeatTypes && courseSeatTypes[0] !== '[]') {
                    if (courseSeatTypes.length === 1) {
                        return courseSeatTypes[0];
                    } else {
                        return courseSeatTypes.join(', ');
                    }
                } else {
                    return null;
                }
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

            /**
             * Open external links in a new tab.
             * Works only for anchor elements that contain 'external-link' class.
             */
            routeToLink: function(e) {
                e.preventDefault();
                e.stopPropagation();
                window.open(e.currentTarget.href);
            },

            render: function() {
                var html,
                    category = this.model.get('category').name,
                    catalogId = '',
                    courseCatalogName = '',
                    invoiceData = this.formatInvoiceData(),
                    emailDomains = this.model.get('email_domains'),
                    lastEdited = this.model.get('last_edited'),
                    templateData,
                    price = null;

                if (this.model.get('price') !== '0.00') {
                    price = _s.sprintf('$%s', this.model.get('price'));
                }

                if (_.isNumber(this.model.get('course_catalog'))) {
                    catalogId = this.model.get('course_catalog');
                    courseCatalogName = ecommerce.coupons.catalogs.get(catalogId).get('name');
                }

                templateData = {
                    category: category,
                    coupon: this.model.toJSON(),
                    courseCatalogName: courseCatalogName,
                    courseSeatType: this.formatSeatTypes(),
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
                this.renderCourseData();
                this.delegateEvents();

                if (this.model.get('catalog_type') === this.model.catalogTypes.multiple_courses) {
                    this.dynamic_catalog_view = new DynamicCatalogView({
                        query: this.model.get('catalog_query'),
                        seat_types: this.model.get('course_seat_types')
                    });

                    this.dynamic_catalog_view.$el = this.$('.catalog_buttons');
                    this.dynamic_catalog_view.render();
                    this.dynamic_catalog_view.delegateEvents();
                }

                this.$('.coupon-information').before(AlertDivTemplate);
                this.$alerts = this.$el.find('.alerts');

                return this;
            },

            renderCourseData: function() {
                if (this.model.get('catalog_type') === 'Single course') {
                    this.$('.course-info').append(
                        _s.sprintf(
                            '<div class="value">%s<span class="pull-right">%s</span></div>',
                            this.model.get('course_id'),
                            this.model.get('seat_type'))
                    );
                }
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
