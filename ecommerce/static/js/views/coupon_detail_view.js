define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/coupon_detail.html'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              CouponDetailTemplate) {
        'use strict';

        return Backbone.View.extend({
            className: 'coupon-detail-view',

            events: {
                'click .voucher-report-button': 'downloadCouponReport'
            },

            template: _.template(CouponDetailTemplate),

            capitalize: function (string) {
                return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
            },

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

            courseID: function(course_data) {
                var course_id = _.findWhere(course_data, {'name': 'course_key'});
                return course_id ? course_id.value : '';
            },

            certificateType: function(course_data) {
                var certificate_type = _.findWhere(course_data, {'name': 'certificate_type'});
                return certificate_type ? gettext(this.capitalize(certificate_type.value)) : '';
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
                    return gettext('Can only be used once per customer');
                }
                return '';
            },

            render: function () {
                var course_data = this.model.get('seats')[0].attribute_values,
                    html,
                    voucher = this.model.get('vouchers')[0],
                    category = this.model.get('categories')[0].name;

                html = this.template({
                    course_id: this.courseID(course_data),
                    certificate_type: this.certificateType(course_data),
                    coupon: this.model.attributes,
                    couponType: this.couponType(voucher),
                    codeStatus: this.codeStatus(voucher),
                    discountValue: this.discountValue(voucher),
                    endDateTime: this.formatDateTime(voucher.end_datetime),
                    lastEdited: this.formatLastEditedData(this.model.get('last_edited')),
                    price: _s.sprintf('$%s', this.model.get('price')),
                    startDateTime: this.formatDateTime(voucher.start_datetime),
                    usage: this.usageLimitation(voucher),
                    category: category
                });

                this.$el.html(html);
                this.renderVoucherTable();
                this.delegateEvents();
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

            downloadCouponReport: function (event) {
                var url = _s.sprintf('/api/v2/coupons/coupon_reports/%d', this.model.id);

                event.preventDefault();
                window.open(url, '_blank');
                return this;
            }
        });
    }
);
