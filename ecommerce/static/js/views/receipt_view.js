define([
      'jquery',
      'backbone',
      'underscore',
      'underscore.string',
      'moment',
      'text!templates/receipt.html',
      'text!templates/_receipt_waiting.html',
      'text!templates/_receipt_error.html',
      'text!templates/_receipt_line.html'
  ],
  function ($,
            Backbone,
            _,
            _s,
            moment,
            ReceiptTemplate,
            WaitingTemplate,
            ErrorTemplate,
            LineTemplate) {
  'use strict';

  return Backbone.View.extend({
    receiptTemplate: _.template(ReceiptTemplate),
    waitingTempalte: _.template(WaitingTemplate),
    errorTemplate: _.template(ErrorTemplate),
    lineTemplate: _.template(LineTemplate),


    initialize: function (options) {
      this.orderNumber = options.orderNumber;
      this.attempts = 0;
    },

    retrieveReceiptData: function () {
      $.ajax({
        url: '/api/v2/orders/' + this.orderNumber,
        method: 'GET',
        context: this,
        success: this.onSuccess,
        error: this.displayError
      });
    },

    formatPaymentMethod: function (paymentMethod) {
      if (paymentMethod) {
        return _s.sprintf('%s %s', paymentMethod.card_type, paymentMethod.number);
      }
      return null;
    },

    getCourseOrg: function(attributes) {
      var courseKeyAttr = _.find(attributes, function(attr) {
          return attr.code === 'course_key'
        }),
        courseKeyOrgRegex = /course-v1:(\w+)\+\w+\+\w+/;
      return courseKeyAttr.value.match(courseKeyOrgRegex)[1];
    },

    appendLineData: function (lines) {
      var context,
          elements = [];
      _.each(lines, function(line) {
        context = {
          'quantity': line.quantity,
          'description': line.description,
          'organization': this.getCourseOrg(line.product.attribute_values),
          'price': line.unit_price_excl_tax
        };
        elements.push(this.lineTemplate(context))
      }, this);
      this.$('.order-lines-data').append(elements);
    },

    getVoucherData: function (vouchers) {
      var stringFormat,
          formattedVouchers = [];

      if (vouchers.length) {
        _.each(vouchers, function(voucher) {
          stringFormat = voucher.benefit.type === 'Percentage' ? '%u%%' : '$%u';
          formattedVouchers.push({
            'code': voucher.code,
            'benefit': _s.sprintf(stringFormat, voucher.benefit.value)
          });
        });
        return formattedVouchers;
      }
      return null;
    },

    formatPrice: function (currency, price) {
      return _s.sprintf('%s %s', currency, Number(price).toFixed(2));
    },

    onSuccess: function (data) {
      var context;
      this.attempts += 1;

      if (data.status === 'Complete') {
        context = {
          'billingAddress': data.billing_address,
          'orderNumber': data.number,
          'userEmail': data.user.email,
          'orderDate': moment(data.date_placed).format('MMM DD, YYYY'),
          'paymentMethod': this.formatPaymentMethod(data.payment_method),
          'subtotalPrice': this.formatPrice(data.currency, data.total_before_discounts_incl_tax),
          'discountPrice': this.formatPrice(data.currency, data.discount),
          'totalPrice': this.formatPrice(data.currency, data.total_excl_tax),
          'voucherData': this.getVoucherData(data.vouchers),
        };
        this.$el.html(this.receiptTemplate(context));
        this.appendLineData(data.lines);
      } else if (data.status === 'Open' && this.attempts < 6) {
        setTimeout($.proxy(this.retrieveReceiptData, this), 2000);
      } else {
        this.displayError();
      }
    },

    displayError: function () {
      this.$el.html(this.errorTemplate);
    },

    render: function () {
      this.$el.html(this.waitingTempalte());
      this.retrieveReceiptData();
      return this;
    }
  });
});
