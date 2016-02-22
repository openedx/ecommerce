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

        var filters = {
            voucher: function(obj){ return obj.name === 'Coupon vouchers'; },
            note: function(obj){ return obj.name === 'Note'; }
        };

        return Backbone.View.extend({
            className: 'coupon-detail-view',

            events: {
                'click .voucher-report-button': 'downloadCouponReport'
            },

            template: _.template(CouponDetailTemplate),

            capitalize: function(string) {
                return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
            },

            codeStatus: function(voucher) {
                var startDate = moment(new Date(voucher.start_datetime)),
                    endDate = moment(new Date(voucher.end_datetime)),
                    in_time_interval = (startDate.isBefore(Date.now()) && endDate.isAfter(Date.now()));
                return gettext(in_time_interval ? 'ACTIVE':'INACTIVE');
            },

            couponType: function(voucher) {
                var benefitType = voucher.benefit[0],
                    benefitValue = voucher.benefit[1];
                return gettext(
                    (benefitType === 'Percentage' && benefitValue === 100) ? 'Enrollment Code':'Discount Code'
                );
            },

            courseID: function(course_data) {
                var course_id = _.findWhere(course_data, {'name': 'course_key'});
                return course_id ? course_id.value : '';
            },

            courseType: function(course_data) {
                var course_type = _.findWhere(course_data, {'name': 'certificate_type'});
                return course_type ? gettext(this.capitalize(course_type.value)) : '';
            },

            discountValue: function(voucher) {
                var benefitType = voucher.benefit[0],
                    benefitValue = voucher.benefit[1];

                return (benefitType === 'Percentage') ? benefitValue + '%':benefitValue;
            },

            formatDateTime: function(dateTime) {
                return moment.utc(dateTime).format('MM/DD/YYYY h:mm A');
            },

            lastEdited: function(last_edited) {
                return last_edited[0] + ' - ' + this.formatDateTime(last_edited[1]);
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
                    voucher = this.model.get('attribute_values').filter(filters.voucher)[0].value[0],
                    note = this.model.get('attribute_values').filter(filters.note);

                note = note.length > 0 ? note[0].value : null;

                html = this.template({
                    course_id: this.courseID(course_data),
                    course_type: this.courseType(course_data),
                    coupon: this.model.attributes,
                    couponType: this.couponType(voucher),
                    codeStatus: this.codeStatus(voucher),
                    discountValue: this.discountValue(voucher),
                    endDateTime: this.formatDateTime(voucher.end_datetime),
                    lastEdited: this.lastEdited(this.model.get('last_edited')),
                    price: '$' + this.model.get('price'),
                    startDateTime: this.formatDateTime(voucher.start_datetime),
                    usage: this.usageLimitation(voucher),
                    note: note
                });
                this.$el.html(html);
                this.renderVoucherTable();
                this.refreshTableData();
                this.delegateEvents();
                return this;
            },

            renderVoucherTable: function () {
                if (!$.fn.dataTable.isDataTable('#vouchersTable')) {
                    this.$el.find('#vouchersTable').DataTable({
                        autoWidth: false,
                        info: true,
                        paging: false,
                        ordering: false,
                        searching: false,
                        columns: [
                            {
                                title: gettext('Code'),
                                data: 'code',
                            },
                            {
                                title: gettext('Redemption URL'),
                                data: 'redeem_url'
                            }
                        ]
                    });
                }
                return this;
            },

            refreshTableData: function () {
                var data = this.model.get('attribute_values').filter(filters.voucher)[0].value,
                    $table = this.$el.find('#vouchersTable').DataTable();

                $table.clear().rows.add(data).draw();
                return this;
            },

            downloadCouponReport: function (event) {
                var url = '/api/v2/coupons/coupon_reports/' + this.model.id;

                event.preventDefault();
                window.open(url, '_blank');
                return this;
            }
        });
    }
);
