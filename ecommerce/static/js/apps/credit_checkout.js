require([
    'jquery',
    'pages/credit_checkout'
],
    function($,
              CreditCheckoutPage) {
        'use strict';

        new CreditCheckoutPage({el: $('.credit-checkout-page')});
    }
);
