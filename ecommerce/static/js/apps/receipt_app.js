require([
        'jquery',
        'routers/receipt_router'
    ],
    function ($,
              ReceiptRouter) {
        'use strict';

        $(function () {
            var receiptApp = new ReceiptRouter({el: $('.receipt')});
            receiptApp.start();
        });
    }
);

