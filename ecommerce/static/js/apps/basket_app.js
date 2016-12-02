require([
        'jquery',
        'pages/basket_page'
    ],
    function ($,
              BasketPage) {
        'use strict';

        /**
         * Configure the payment form event handlers.
         */
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
                var cardExpiryMonth = $('select[name=card_expiry_month]').val();
                var cardExpiryYear = $('select[name=card_expiry_year]').val();
                if (/^[0-9]$/.test(parseInt(cardExpiryMonth))) {
                    cardExpiryMonth = '0' + cardExpiryMonth;
                }
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
                    error: function (jqXHR, textStatus, errorThrown) {
                        // TODO Handle errors. Ideally the form should be validated in JavaScript
                        // before it is submitted.
                        console.log(jqXHR);
                        console.log(textStatus);
                        console.log(errorThrown);

                        // Don't allow the form to submit.
                        event.stopPropagation();
                    }
                });
            });
        }

        $(document).ready(function () {
            BasketPage.onReady();
            initializePaymentForm();
        });
    }
);
