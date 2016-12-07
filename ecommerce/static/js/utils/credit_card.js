define([],function () {
        'use strict';

        return {
            /**
             * Most performant Luhn check for credit card number validity.
             * https://jsperf.com/credit-card-validator/7
             */
            isValidCardNumber: function(cardNumber) {
                var len = cardNumber.length,
                    mul = 0,
                    prodArr = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [0, 2, 4, 6, 8, 1, 3, 5, 7, 9]],
                    sum = 0;

                while (len--) {
                    sum += prodArr[mul][parseInt(cardNumber.charAt(len), 10)];
                    mul ^= 1;
                }

                return sum % 10 === 0 && sum > 0;
            },

            /**
             * Get the credit card type based on the card's number.
             *
             * @param (string) - The credit card number.
             *
             * @returns (object) - The credit card type name and coresponding 3-number CyberSource card ID.
             */
            getCreditCardType: function(cardNumber) {
                var matchers = {
                    amex: {
                        regex: /^3[47]\d{13}$/,
                        cybersourceTypeId: '003',
                        cvnLength: 4
                    },
                    diners: {
                        regex: /^3(?:0[0-59]|[689]\d)\d{11}$/,
                        cybersourceTypeId: '005',
                        cvnLength: 3
                    },
                    discover: {
                        regex: /^(6011\d{2}|65\d{4}|64[4-9]\d{3}|62212[6-9]|6221[3-9]\d|622[2-8]\d{2}|6229[01]\d|62292[0-5])\d{10,13}$/,  // jshint ignore:line
                        cybersourceTypeId: '004',
                        cvnLength: 3
                    },
                    jcb: {
                        regex: /^(?:2131|1800|35\d{3})\d{11}$/,
                        cybersourceTypeId: '007',
                        cvnLength: 4
                    },
                    maestro: {
                        regex: /^(5[06789]|6\d)[0-9]{10,17}$/,
                        cybersourceTypeId: '042',
                        cvnLength: 3
                    },
                    mastercard: {
                        regex: /^(5[1-5]\d{2}|222[1-9]|22[3-9]\d|2[3-6]\d{2}|27[01]\d|2720)\d{12}$/,
                        cybersourceTypeId: '002',
                        cvnLength: 3
                    },
                    visa: {
                        regex: /^(4\d{12}?(\d{3})?)$/,
                        cybersourceTypeId: '001',
                        cvnLength: 3
                    }
                };

                for (var key in matchers) {
                    if (matchers[key].regex.test(cardNumber)) {
                        return {
                            'name': key,
                            'type': matchers[key].cybersourceTypeId,
                            'cvnLength': matchers[key].cvnLength
                        };
                    }
                }
            }
        };
    }
);
