define([
        'jquery',
        'underscore',
        'backbone'
    ],
    function ($,
              _,
              Backbone
    ) {
        'use strict';

        return Backbone.View.extend({
            events: {
                'click .spinner .btn:first-of-type': 'incrementQuantity',
                'click .spinner .btn:last-of-type': 'decrementQuantity',
                'click #voucher_form_link a': 'showVoucherForm',
                'click #voucher_form_cancel': 'hideVoucherForm'
            },

            incrementQuantity: function (event) {
                // Increment the quantity field until max
                var btn = $(event.currentTarget);
                var input = btn.closest('.spinner').find('input');
                // Stop if max attribute is defined and value is reached to given max value
                if (input.attr('max') === undefined || parseInt(input.val()) < parseInt(input.attr('max'))) {
                    input.val(parseInt(input.val()) + 1);
                } else {
                    btn.next('disabled', true);
                }
            },

            decrementQuantity: function (event) {
                // Decrement the quantity field until min
                var btn = $(event.currentTarget);
                var input = btn.closest('.spinner').find('input');
                // Stop if min attribute is defined and value is reached to given min value
                if (input.attr('min') === undefined || parseInt(input.val()) > parseInt(input.attr('min'))) {
                    input.val(parseInt(input.val()) - 1);
                } else {
                    btn.prev('disabled', true);
                }
            },

            hideVoucherForm: function (event) {
                event.preventDefault();
                $('#voucher_form_container').hide();
                $('#voucher_form_link').show();
            },

            showVoucherForm: function (event) {
                event.preventDefault();
                $('#voucher_form_container').show();
                $('#voucher_form_link').hide();
                $('#id_code').focus();
            }
        });
    });
