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
                this.view = new ReceiptView(options);
                this.view.render();
            }
        });
    }
);
