require([
        'jquery',
        'pages/basket_page'
    ],
    function ($,
              BasketPage) {
        'use strict';

        $(document).ready(BasketPage.onReady);

        $(document).ready(function(){

            $(".quantity").keyup(function (){
                this.value = this.value.replace(/[^0-9\.]/g,'');
            });
            $(".up").click(function(){
                var quantity = parseInt($(this).siblings(".quantity").val());
                $(this).siblings(".quantity").val(quantity + 1);
            });
            $(".down").click(function(){
                var quantity = parseInt($(this).siblings(".quantity").val());
                if (quantity > 1) {
                    $(this).siblings(".quantity").val(quantity - 1);
                }
            });

            $('div.payment-buttons').on('click', function(e) {
                resetAdyenFormValidation();
            });

            $('div.checkout-buttons-section .checkout-button').on('click', function(e) {
                var basketId = $('.checkout-buttons-section').data('basket-id');
                $('#messages').empty();

                validateRequiredFields();
                validateEmail($("#email")[0]);
                validateCardHolderName($("#card_holder_name")[0]);
                validateCardNumber($("#card_number")[0]);
                validateCardCVC($("#card_cvc")[0]);
                validateCardExpiryMonth($("#card_expiry_month")[0]);
                validateCardExpiryYear($("#card_expiry_year")[0]);
            });

            $('input.required').on('focusout', function(e) {
                var el = e.currentTarget;
                validateRequiredField(el);
            });

            $('input.name').on('focusout', function(e) {
                var fullName = $("#first_name").val().trim() + ' ' + $("#last_name").val().trim();
                $("#card_holder_name").val(fullName);
            });

            $("#email").focusout(function(){
                this.value = this.value.trim();
                validateEmail(this);
            });

            $("#card_holder_name").focusout(function(){
                this.value = this.value.trim();
                validateCardHolderName(this);
            });

            $("#card_number").focusout(function(){
                validateCardNumber(this);
            });

            $("#card_cvc").focusout(function() {
                validateCardCVC(this);
            });

            $("#card_expiry_month").focusout(function() {
                validateCardExpiryMonth(this);
            });

            $("#card_expiry_year").focusout(function() {
                validateCardExpiryYear(this);
            });

            $('#adyen-encrypted-form').on('submit', function (e) {
                var formData;
                e.preventDefault();
                if ($('form#adyen-encrypted-form div.form-field.has-error').length == 0) {
                    formData = $('form#adyen-encrypted-form').serializeArray();
                    formData.push(
                        getAdyenFormFieldByID('first_name'),
                        getAdyenFormFieldByID('last_name'),
                        getAdyenFormFieldByID('email'),
                        getAdyenFormFieldByID('address'),
                        getAdyenFormFieldByID('appartment'),
                        getAdyenFormFieldByID('city'),
                        getAdyenFormFieldByID('state'),
                        getAdyenFormFieldByID('country'),
                        getAdyenFormFieldByID('zip_code')
                    );
                    $.post( $('form#adyen-encrypted-form').attr('action'), formData );
                }
            });

            function getAdyenFormFieldByID(fieldId) {
                return {name: fieldId, value: $('form#adyen-encrypted-form #' + fieldId).val()};
            }

            function validateEmail(el) {
                var re = /^([\w-]+(?:\.[\w-]+)*)@((?:[\w-]+\.)*\w[\w-]{0,66})\.([a-z]{2,6}(?:\.[a-z]{2})?)$/i;
                if (!re.test(el.value)){
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function validateRequiredFields() {
                Array.prototype.slice.call(
                    $('input.required')
                ).forEach(function (el) {
                    validateRequiredField(el);
                });
            }

            function validateRequiredField(el) {
                if (el.value.trim() == '') {
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function validateCardHolderName(el) {
                if (el.value.length < 1 || el.value.length > 20) {
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function validateCardNumber(el) {
                var cardNumberRegex = new RegExp("^[0-9]{16}$");
                if (!cardNumberRegex.test(el.value) || !luhnCheck(el.value)){
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function validateCardCVC(el) {
                var cardCvcRegex = new RegExp("^[0-9]{3,4}$");
                if (!cardCvcRegex.test(el.value)) {
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function validateCardExpiryMonth(el) {
                if (el.value.length == 0) {
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function validateCardExpiryYear(el) {
                if (el.value.length == 0) {
                    showValidationError(el);
                } else {
                    hideValidationError(el);
                }
            }

            function luhnCheck(val) {
                var sum = 0;
                for (var i = 0; i < val.length; i++) {
                    var intVal = parseInt(val.substr(i, 1));
                    if (i % 2 == 0) {
                        intVal *= 2;
                        if (intVal > 9) {
                            intVal = 1 + (intVal % 10);
                        }
                    }
                    sum += intVal;
                }
                return (sum % 10) == 0;
            }

            function showValidationError(el) {
                el.closest('div.form-field').classList.add('has-error');
            }

            function hideValidationError(el) {
                el.closest('div.form-field').classList.remove('has-error');
            }

            function resetAdyenFormValidation() {
                $('form#adyen-encrypted-form .form-field').removeClass('has-error');
            }
        });
    }
);

