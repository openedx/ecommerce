define([
    'jquery',
    'backbone',
    'ecommerce',
    'underscore',
    'underscore.string',
    'views/coupon_detail_view',
    'text!templates/_alert_div.html',
    'text!templates/enterprise_coupon_detail.html'
],
    function($,
              Backbone,
              ecommerce,
              _,
              _s,
              CouponDetailView,
              AlertDivTemplate,
              EnterpriseCouponDetailTemplate) {
        'use strict';

        return CouponDetailView.extend({
            template: _.template(EnterpriseCouponDetailTemplate),

            usageLimitation: function() {
                var message = this._super();
                if (!message) {
                    if (this.model.get('voucher_type') === 'Multi-use-per-Customer') {
                        message = gettext('Can be used multiple times by one customer');
                    }
                }
                return message;
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
            }
        });
    }
);
