define([
        'jquery',
        'backbone',
        'adyen/encrypt',
        'bootstrap_validator'
    ],
    function ($,
              Backbone,
              AdyenEncrypt
    ) {
        'use strict';

        return Backbone.View.extend({
            events: {
            },

            initialize: function() {
                var self = this;
                // Add client-side encryption of payment details
                AdyenEncrypt.createEncryptedForm(this.el, window.adyenCSEPublicKey, {});
                // Add payment form validation
                $(this.el).validator();
            }
        });
    });
