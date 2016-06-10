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

            codeStatus: function (voucher) {
                var startDate = moment(new Date(voucher.start_datetime)),
                    endDate = moment(new Date(voucher.end_datetime)),
                    in_time_interval = (startDate.isBefore(Date.now()) && endDate.isAfter(Date.now()));
                return gettext(in_time_interval ? 'ACTIVE' : 'INACTIVE');
            },

            couponType: function (voucher) {
                var benefitType = voucher.benefit[0],
                    benefitValue = voucher.benefit[1];
                return gettext(
                    (benefitType === 'Percentage' && benefitValue === 100) ? 'Enrollment Code' : 'Discount Code'
                );
            },

            discountValue: function(voucher) {
                var benefitType = voucher.benefit[0],
                    benefitValue = voucher.benefit[1],
                    stringFormat = (benefitType === 'Percentage') ? '%u%%' : '$%u';
                return _s.sprintf(stringFormat, benefitValue);
            },

            formatDateTime: function(dateTime) {
                if (dateTime) {
                    return moment.utc(dateTime).format('MM/DD/YYYY h:mm A');
                }
                return null;
            },

            formatLastEditedData: function(last_edited) {
                return _s.sprintf('%s - %s', last_edited[0], this.formatDateTime(last_edited[1]));
            },

            usageLimitation: function(voucher) {
                if (voucher.usage === 'Single use') {
                    return gettext('Can be used once by one customer');
                } else if (voucher.usage === 'Multi-use') {
                    return gettext('Can be used multiple times by multiple customers');
                } else if (voucher.usage === 'Once per customer') {
                    return gettext('Can be used once by multiple customers');
                }
                return '';
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

            render: function () {
                var html,
                    voucher = this.model.get('vouchers')[0],
                    category = this.model.get('categories')[0].name,
                    note = this.model.get('note'),
                    invoice_type = this.model.get('invoice_type'),
                    invoice_number = this.model.get('invoice_number'),
                    invoice_payment_date = this.model.get('invoice_payment_date'),
                    invoice_discount_type = this.model.get('invoice_discount_type'),
                    invoice_discount_value = this.model.get('invoice_discount_value'),
                    invoiced_amount = this.model.get('invoiced_amount'),
                    tax_deducted_source_value = this.model.get('tax_deducted_source_value');

                if (invoice_discount_value === null) {
                    invoice_discount_type = null;
                } else  {
                    invoice_discount_value = this.invoiceDiscountValue(invoice_discount_type, invoice_discount_value);
                }
                tax_deducted_source_value = this.taxDeductedSource(tax_deducted_source_value);

                html = this.template({
                    coupon: this.model.toJSON(),
                    couponType: this.couponType(voucher),
                    codeStatus: this.codeStatus(voucher),
                    discountValue: this.discountValue(voucher),
                    endDateTime: this.formatDateTime(voucher.end_datetime),
                    lastEdited: this.formatLastEditedData(this.model.get('last_edited')),
                    price: _s.sprintf('$%s', this.model.get('price')),
                    startDateTime: this.formatDateTime(voucher.start_datetime),
                    usage: this.usageLimitation(voucher),
                    category: category,
                    note: note,
                    invoice_type: invoice_type,
                    invoice_number: invoice_number,
                    invoice_payment_date: this.formatDateTime(invoice_payment_date),
                    invoice_discount_type: invoice_discount_type,
                    invoice_discount_value: invoice_discount_value,
                    invoiced_amount: invoiced_amount,
                    tax_deducted_source_value: tax_deducted_source_value
                });

                this.$el.html(html);
                this.renderVoucherTable();
                this.renderCourseData();
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

            renderVoucherTable: function () {
                this.$el.find('#vouchersTable').DataTable({
                    autoWidth: false,
                    info: true,
                    paging: false,
                    ordering: false,
                    searching: false,
                    columns: [
                        {
                            title: gettext('Code'),
                            data: 'code'
                        },
                        {
                            title: gettext('Redemption URL'),
                            data: 'redeem_url'
                        }
                    ],
                    data: this.model.get('vouchers')
                });
                return this;
            },

            renderCourseData: function () {
                if (this.model.get('catalog_type') === 'Single course') {
                    this.$el.find('.course-info').append(
                        _s.sprintf(
                            '<div class="value">%s<span class="pull-right">%s</span></div>',
                            this.model.get('course_id'),
                            this.model.get('seat_type'))
                    );

                    this.$el.find('.catalog-query').addClass('hidden');
                    this.$el.find('.seat-types').addClass('hidden');
                    this.$el.find('.course-info').removeClass('hidden');
                } else if (this.model.get('catalog_type') === 'Multiple courses') {
                    this.$el.find('.course-info').addClass('hidden');
                    this.$el.find('.catalog-query').removeClass('hidden');
                    this.$el.find('.seat-types').removeClass('hidden');
                }
                return this;
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
