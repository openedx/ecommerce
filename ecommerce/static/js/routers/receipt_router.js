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
                'receipt/?order_number=:order': 'showReceiptPage'
            },

            showReceiptPage: function() {
                var page = new ReceiptPage();
                this.currentView = page;
                //this.$el.html(page.el); Restore this once figure out what we want to render
            }
        });
    }
);
