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
                AdyenEncrypt.createEncryptedForm(this.el, window.adyenCSEPublicKey, {
                    onsubmit: function(event) {
                        self.handleSubmit(event);
                    }
                });
                $(this.el).validator();
            }
        });
    });
