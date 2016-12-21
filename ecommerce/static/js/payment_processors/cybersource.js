/**
 * CyberSource payment processor specific actions.
 */
require([
        'jquery',
        'pages/basket_page'
    ], function(
        $,
        BasketPage
    ) {
    'use strict';

    function initializePaymentForm() {
        var signingUrl,
            $paymentForm = $('.payment-form');

        if ($paymentForm.length < 1) {
            return;
        }

        signingUrl = $paymentForm.data('signing-url');

        $paymentForm.submit(function (event) {
            var $signedFields = $('input,select', $paymentForm).not('.pci-field');

            // Format the date to a format that CyberSource accepts (MM-YYYY).
            var cardExpiryMonth = $('select[name=card_expiry_month]').val(),
                cardExpiryYear = $('select[name=card_expiry_year]').val();
            $('input[name=card_expiry_date]').val(cardExpiryMonth + '-' + cardExpiryYear);

            // Post synchronously since we need the returned data.
            $.ajax({
                type: 'POST',
                url: signingUrl,
                data: $signedFields.serialize(),
                async: false,
                success: function (data) {
                    var formData = data.form_fields;

                    // Disable the fields on the form so they are not posted since their names are not what is
                    // expected by CyberSource. Instead post add the parameters from the server to the form,
                    // and post them.
                    $signedFields.attr('disabled', 'disabled');

                    for (var key in formData) {
                        if (formData.hasOwnProperty(key)) {
                            $paymentForm.append(
                                '<input type="hidden" name="' + key + '" value="' + formData[key] + '" />'
                            );
                        }
                    }
                },
                error: function (jqXHR, textStatus) {
                    // Don't allow the form to submit.
                    event.preventDefault();
                    event.stopPropagation();

                    var cardHolderFields = [
                        'first_name', 'last_name', 'address_line1', 'address_line2',
                        'state', 'city', 'country', 'postal_code'
                    ];

                    if (textStatus === 'error') {
                        var error = JSON.parse(jqXHR.responseText);
                        if (error.field_errors) {
                            for (var k in error.field_errors) {
                                if (cardHolderFields.indexOf(k) !== -1) {
                                    var field = $('input[name=' + k + ']');
                                    BasketPage.appendCardHolderValidationErrorMsg(field, error.field_errors[k]);
                                    field.focus();
                                }
                            }
                        }
                    }
                }
            });
        });
    }

    $(document).ready(function () {
        initializePaymentForm();
    });
});
