/* global Cybersource */
/**
 * CyberSource payment processor specific actions.
 */
require([
    'jquery',
    'pages/basket_page'
], function($, BasketPage) {
    'use strict';

    var CyberSourceClient = {
        init: function() {
            var $paymentForm = $('#paymentForm'),
                $pciFields = $('.pci-field', $paymentForm),
                cardMap = {
                    visa: '001',
                    mastercard: '002',
                    amex: '003',
                    discover: '004'
                };

            this.signingUrl = Cybersource.signingUrl;   // jshint ignore:line

            // The payment form should post to CyberSource
            $paymentForm.attr('action', Cybersource.postUrl);   // jshint ignore:line

            // Add name attributes to the PCI fields
            $pciFields.each(function() {
                var $this = $(this);
                $this.attr('name', $this.data('name'));
            });

            $paymentForm.submit($.proxy(this.onSubmit, this));

            // Add CyberSource-specific fields
            $paymentForm.append($('<input type="hidden" name="card_expiry_date" class="pci-field">'));
            $paymentForm.append($('<input type="hidden" name="card_type" class="pci-field">'));

            // Add an event listener to populate the CyberSource card type field
            $paymentForm.on('cardType:detected', function(event, data) {
                $('input[name=card_type]', $paymentForm).val(cardMap[data.type]);
            });
        },

        /**
         * Payment form submit handler.
         *
         * Before posting to CyberSource, this handler retrieves signed data fields from the server. PCI fields
         * (e.g. credit card number, expiration) should NEVER be posted to the server, only to CyberSource.
         *
         * @param event
         */
        onSubmit: function(event) {
            var $form = $(event.target),
                $signedFields = $('input,select', $form).not('.pci-field'),
                expMonth = $('#card-expiry-month', $form).val(),
                expYear = $('#card-expiry-year', $form).val();

            // Restore name attributes so the data can be posted to CyberSource
            $('#card-number', $form).attr('name', 'card_number');
            $('#card-cvn', $form).attr('name', 'card_cvn');

            // Post synchronously since we need the returned data.
            $.ajax({
                type: 'POST',
                url: this.signingUrl,
                data: $signedFields.serialize(),
                async: false,
                success: function(data) {
                    var formData = data.form_fields,
                        key;

                    // Format the date for CyberSource (MM-YYYY)
                    $('input[name=card_expiry_date]', $form).val(expMonth + '-' + expYear);

                    // Disable the fields on the form so they are not posted since their names are not what is
                    // expected by CyberSource. Instead post add the parameters from the server to the form,
                    // and post them.
                    $signedFields.attr('disabled', 'disabled');

                    // eslint-disable-next-line no-restricted-syntax
                    for (key in formData) {
                        if (Object.prototype.hasOwnProperty.call(formData, key)) {
                            $form.append(
                                '<input type="hidden" name="' + key + '" value="' + formData[key] + '" />'
                            );
                        }
                    }
                },

                error: function(jqXHR, textStatus) {
                    var $field,
                        cardHolderFields,
                        error,
                        k;

                    // Don't allow the form to submit.
                    event.preventDefault();
                    event.stopPropagation();

                    cardHolderFields = [
                        'first_name', 'last_name', 'address_line1', 'address_line2', 'state', 'city', 'country',
                        'postal_code'
                    ];

                    if (textStatus === 'error') {
                        error = JSON.parse(jqXHR.responseText);

                        if (error.field_errors) {
                            // eslint-disable-next-line no-restricted-syntax
                            for (k in error.field_errors) {
                                if (cardHolderFields.indexOf(k) !== -1) {
                                    $field = $('input[name=' + k + ']');
                                    // TODO Use custom events to remove this dependency.
                                    BasketPage.appendCardHolderValidationErrorMsg($field, error.field_errors[k]);
                                    $field.focus();
                                }
                            }
                        } else {
                            // Unhandled errors should redirect to the general payment error page.
                            window.location.href = window.paymentErrorPath;
                        }
                    }
                }
            });
        }
    };

    $(document).ready(function() {
        CyberSourceClient.init();
    });
});
