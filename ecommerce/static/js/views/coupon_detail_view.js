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

            capitalize: function(string) {
                return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
            },

            codeStatus: function(voucher) {
                var endDate = moment(new Date(voucher.end_datetime));
                return gettext((endDate.isAfter(Date.now())) ? 'ACTIVE':'INACTIVE');
            },

            couponType: function(voucher) {
                var benefitType = voucher.benefit[0],
                    benefitValue = voucher.benefit[1];
                return gettext(
                    (benefitType === 'Percentage' && benefitValue === 100) ? 'Enrollment Code':'Discount Code'
                );
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
                var course_data = this.model.get('seats')[0],
                    html,
                    voucher = this.model.get('vouchers')[0];

                html = this.template({
                    course_id: course_data.attribute_values[1].value,
                    course_type: gettext(this.capitalize(course_data.attribute_values[0].value)),
                    coupon: this.model.attributes,
                    couponType: this.couponType(voucher),
                    codeStatus: this.codeStatus(voucher),
                    discountValue: this.discountValue(voucher),
                    endDateTime: this.formatDateTime(voucher.end_datetime),
                    lastEdited: this.lastEdited(this.model.get('last_edited')),
                    price: '$' + this.model.get('price'),
                    startDateTime: this.formatDateTime(voucher.start_datetime),
                    usage: this.usageLimitation(voucher)
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
                var data = this.model.get('vouchers'),
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
