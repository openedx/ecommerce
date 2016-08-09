define([
        'jquery',
        'backbone',
        'adyen/views/card_payment_view'
    ],
    function ($,
              Backbone,
              CardPaymentView
    ) {
        'use strict';

        return Backbone.View.extend({
            events: {
                'click .payment-method-btns .btn': 'handlePaymentMethodSelection'
            },

            initialize: function() {
                var $el = $(this.el);
                this.$paymentMethodBtns = $el.find('.payment-method-btns .btn');
                this.$paymentMethodViews = $el.find('.payment-view');
                this.card_payment_view = new CardPaymentView({el: $('#card-payment-view')});

                // Select the appropriate view if the current location has a hash
                // Default to the first payment view
                var selectedPaymentMethodId = window.location.hash || '#' + this.$paymentMethodViews.attr('id');
                if (selectedPaymentMethodId) {
                    this.selectPaymentMethodButton(
                        $el.find('.payment-method-btns .btn[href="' + selectedPaymentMethodId + '"]')
                    );
                    this.selectPaymentMethodView($el.find(selectedPaymentMethodId));
                }
            },

            handlePaymentMethodSelection: function(event) {
                var $selectedPaymentMethodBtn = $(event.currentTarget).closest('.btn'),
                    $selectedPaymentMethodView = this.$paymentMethodViews.filter(
                        $selectedPaymentMethodBtn.attr('href')
                    );

                this.selectPaymentMethodButton($selectedPaymentMethodBtn);
                this.selectPaymentMethodView($selectedPaymentMethodView);
            },

            selectPaymentMethodButton: function($paymentMethodBtn) {
                // Toggle selected class on payment method buttons
                this.$paymentMethodBtns.filter('.selected').removeClass('selected');
                $paymentMethodBtn.addClass('selected');
            },

            selectPaymentMethodView: function($paymentMethodView) {
                // Toggle selected class on payment method views
                this.$paymentMethodViews.filter('.selected').removeClass('selected');
                $paymentMethodView.addClass('selected');
            }
        });
    });
