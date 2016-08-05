require([
        'jquery',
        'adyen/views/payment_view'
    ],
    function ($,
              PaymentView) {
        'use strict';
        
        new PaymentView({el: $('#adyen-payment')});
    }
);
