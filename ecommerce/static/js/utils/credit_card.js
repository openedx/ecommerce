define([], function() {
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

            while (len) {
                len -= 1;
                sum += prodArr[mul][parseInt(cardNumber.charAt(len), 10)];
                mul ^= 1; // eslint-disable-line no-bitwise
            }

            return sum % 10 === 0 && sum > 0;
        },

            /**
             * Get the credit card type based on the card number.
             *
             * @param cardNumber (string) - The credit card number.
             *
             * @returns (object) - The credit card type name and CVN length.
             */
        getCreditCardType: function(cardNumber) {
            var key,
                matchers = {
                    amex: {
                        regex: /^3[47]\d{13}$/,
                        cvnLength: 4
                    },
                    discover: {
                        regex: /^(6011\d{2}|65\d{4}|64[4-9]\d{3}|62212[6-9]|6221[3-9]\d|622[2-8]\d{2}|6229[01]\d|62292[0-5])\d{10,13}$/,  // eslint-disable-line max-len
                        cvnLength: 3
                    },
                    mastercard: {
                        regex: /^(5[1-5]\d{2}|222[1-9]|22[3-9]\d|2[3-6]\d{2}|27[01]\d|2720)\d{12}$/,
                        cvnLength: 3
                    },
                    visa: {
                        regex: /^(4\d{12}?(\d{3})?)$/,
                        cvnLength: 3
                    }
                };

            // eslint-disable-next-line no-restricted-syntax
            for (key in matchers) {
                if (matchers[key].regex.test(cardNumber)) {
                    return {
                        name: key,
                        cvnLength: matchers[key].cvnLength
                    };
                }
            }

            return undefined;
        }
    };
}
);
