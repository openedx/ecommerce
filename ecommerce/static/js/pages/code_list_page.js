define([
        'views/code_list_view',
        'pages/page'
    ],
    function (CodeListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Enrollment Codes'),

            initialize: function () {
                this.view = new CodeListView();
                this.render();
            }
        });
    }
);
