define([
        'routers/page_router',
        'pages/receipt_page'
    ],
    function (PageRouter,
              ReceiptPage) {
        'use strict';

        return PageRouter.extend({

            // Base/root path of the app
            root: '/checkout/',

            routes: {
                'receipt/?order_number=:orderNumber': 'showReceiptPage'
            },

            showReceiptPage: function(orderNumber) {
                var page = new ReceiptPage({orderNumber: orderNumber});
                this.currentView = page;
            }
        });
    }
);
