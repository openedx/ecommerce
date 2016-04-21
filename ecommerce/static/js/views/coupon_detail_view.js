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
                return moment.utc(dateTime).format('MM/DD/YYYY h:mm A');
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

            render: function () {
                var html,
                    voucher = this.model.get('vouchers')[0],
                    category = this.model.get('categories')[0].name,
                    note = this.model.get('note');

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
