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
                'receipt/?order_number=:order': 'showReceiptPage',
                'payment-details/': 'index'
            },

            index: function() {
              console.log('Triggered');
            },
            showReceiptPage: function() {
                var page = new ReceiptPage();
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
