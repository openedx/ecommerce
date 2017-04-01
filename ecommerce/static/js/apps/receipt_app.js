require([
        'jquery',
        'routers/receipt_router'
    ],
    function ($,
              ReceiptRouter) {
        'use strict';

        $(function () {
            var $app = $('#receipt-page'),
                receiptApp = new ReceiptRouter({$el: $app});
            receiptApp.start();
        });
    }
);
