define([
        'views/receipt_view',
        'pages/page'
    ],
    function (ReceiptView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Receipt'),

            initialize: function (options) {
                this.view = new ReceiptView({orderNumber: options.orderNumber});
                this.render();
            }
        });
    }
);
