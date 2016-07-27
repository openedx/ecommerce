define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/coupon_detail.html',
        'views/dynamic_catalog_view',
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              CouponDetailTemplate,
              DynamicCatalogView) {
        'use strict';

        return Backbone.View.extend({
            className: 'coupon-detail-view',

            events: {
                'click .voucher-report-button': 'downloadCouponReport'
            },

            template: _.template(CouponDetailTemplate),

            formatDateTime: function(dateTime) {
                return moment.utc(dateTime).format('MM/DD/YYYY h:mm A');
            },

            formatLastEditedData: function(last_edited) {
                return _s.sprintf('%s - %s', last_edited[0], this.formatDateTime(last_edited[1]));
            },

            discountValue: function() {
                var stringFormat = (this.model.get('benefit_type') === 'Percentage') ? '%u%%' : '$%u';
                return _s.sprintf(stringFormat, this.model.get('benefit_value'));
            },

            taxDeductedSource: function(value) {
                if (value) {
                    return _s.sprintf('%u%%', parseInt(value));
                } else {
                    return null;
                }
            },

            invoiceDiscountValue: function(type, value) {
                var stringFormat = (type === 'Percentage') ? '%u%%' : '$%u';
                return _s.sprintf(stringFormat, parseInt(value));
            },

            formatInvoiceData: function() {
                var invoice_payment_date = this.model.get('invoice_payment_date'),
                    invoice_discount_type = this.model.get('invoice_discount_type'),
                    invoice_discount_value = this.model.get('invoice_discount_value'),
                    tax_deducted_source = this.model.get('tax_deducted_source');
                
                if (invoice_discount_value === null) {
                    invoice_discount_type = null;
                } else  {
                    invoice_discount_value = this.invoiceDiscountValue(invoice_discount_type, invoice_discount_value);
                }
                tax_deducted_source = this.taxDeductedSource(tax_deducted_source);

                if (invoice_payment_date) {
                    invoice_payment_date = this.formatDateTime(invoice_payment_date);
                }

                return {
                    'invoice_type': this.model.get('invoice_type'),
                    'invoice_number': this.model.get('invoice_number'),
                    'invoice_payment_date': invoice_payment_date,
                    'invoice_discount_type': invoice_discount_type,
                    'invoice_discount_value': invoice_discount_value,
                    'invoiced_amount': this.model.get('invoiced_amount'),
                    'tax_deducted_source_value': tax_deducted_source,
                };
            },

            formatSeatTypes: function() {
                var courseSeatTypes = this.model.get('course_seat_types');
                if (courseSeatTypes) {
                    if(courseSeatTypes.length === 1){
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

            render: function () {
                var html,
                    category = this.model.get('categories')[0].name,
                    invoice_data = this.formatInvoiceData(),
                    template_data;

                template_data = {
                    category: category,
                    coupon: this.model.toJSON(),
                    courseSeatType: this.formatSeatTypes(),
                    discountValue: this.discountValue(),
                    endDateTime: this.formatDateTime(this.model.get('end_date')),
                    lastEdited: this.formatLastEditedData(this.model.get('last_edited')),
                    price: _s.sprintf('$%s', this.model.get('price')),
                    startDateTime: this.formatDateTime(this.model.get('start_date')),
                    usage: this.usageLimitation()
                };

                $.extend(template_data, invoice_data);
                html = this.template(template_data);

                this.$el.html(html);
                this.renderCourseData();
                this.renderInvoiceData();
                this.delegateEvents();

                this.dynamic_catalog_view = new DynamicCatalogView({
                    'query': this.model.get('catalog_query'),
                    'seat_types': this.model.get('course_seat_types')
                });

                this.dynamic_catalog_view.$el = this.$('.catalog_buttons');
                this.dynamic_catalog_view.render();
                this.dynamic_catalog_view.delegateEvents();
                return this;
            },

            renderCourseData: function () {
                if (this.model.get('catalog_type') === 'Single course') {
                    this.$('.course-info').append(
                        _s.sprintf(
                            '<div class="value">%s<span class="pull-right">%s</span></div>',
                            this.model.get('course_id'),
                            this.model.get('seat_type'))
                    );

                    this.$('.catalog-query').addClass('hidden');
                    this.$('.seat-types').addClass('hidden');
                    this.$('.course-info').removeClass('hidden');
                } else if (this.model.get('catalog_type') === 'Multiple courses') {
                    this.$('.course-info').addClass('hidden');
                    this.$('.catalog-query').removeClass('hidden');
                    this.$('.seat-types').removeClass('hidden');
                }
                return this;
            },

            renderInvoiceData: function() {
                var invoice_type = this.model.get('invoice_type'),
                    tax_deducted = this.model.get('tax_deduction'),
                    prepaid_fields = [
                        '.invoice-number',
                        '.invoiced-amount',
                        '.invoice-payment-date'
                    ],
                    postpaid_fields = [
                        '.invoice-discount-type',
                        '.invoice-discount-value'
                    ];
                if (tax_deducted === 'Yes') {
                    this.$('.tax-deducted-source-value').removeClass('hidden');
                } else if (tax_deducted === 'No') {
                    this.$('.tax-deducted-source-value').addClass('hidden');
                }

                if (invoice_type === 'Prepaid') {
                    _.each(prepaid_fields, function(field) {
                        this.$(field).removeClass('hidden');
                    }, this);
                    _.each(postpaid_fields, function(field) {
                        this.$(field).addClass('hidden');
                    }, this);
                } else if (invoice_type === 'Postpaid') {
                    _.each(prepaid_fields, function(field) {
                        this.$(field).addClass('hidden');
                    }, this);
                    _.each(postpaid_fields, function(field) {
                        this.$(field).removeClass('hidden');
                    }, this);
                } else if (invoice_type === 'Not-Applicable') {
                    _.each(prepaid_fields, function(field) {
                        this.$(field).addClass('hidden');
                    }, this);
                    _.each(postpaid_fields, function(field) {
                        this.$(field).addClass('hidden');
                    }, this);
                }
            },

            downloadCouponReport: function (event) {
                var url = _s.sprintf('/api/v2/coupons/coupon_reports/%d', this.model.id);

                event.preventDefault();
                window.open(url, '_blank');
                return this;
            }
        });
    }
);
