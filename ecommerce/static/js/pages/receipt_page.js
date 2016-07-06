define([
        'views/receipt_view',
        'pages/page'
    ],
    function (ReceiptView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Thank You'),

            initialize: function () {
                this.view = new ReceiptView();
                this.render();
            }
        });
    }
);
