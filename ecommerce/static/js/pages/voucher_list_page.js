define([
        'views/voucher_list_view',
        'pages/page'
    ],
    function (VoucherListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Vouchers'),

            initialize: function () {
                this.view = new VoucherListView();
                this.render();
            }
        });
    }
);
