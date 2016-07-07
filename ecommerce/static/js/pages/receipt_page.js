define([
        'views/receipt_view',
        'pages/page'
    ],
    function (ReceiptView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Receipt'),

            initialize: function () {
                this.view = new ReceiptView();
                this.render();
            }
        });
    }
);
