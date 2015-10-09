define([
        'views/voucher_create_view',
        'pages/page'
    ],
    function (VoucherCreateView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Voucher'),

            initialize: function () {
                this.view = new VoucherCreateView();
                this.render();
            }
        });
    }
);
