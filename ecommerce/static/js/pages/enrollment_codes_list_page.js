define([
        'views/enrollment_codes_list_view',
        'pages/page'
    ],
    function (EnrollmentCodesListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Enrollment Codes'),

            initialize: function () {
                this.view = new EnrollmentCodesListView();
                this.render();
            }
        });
    }
);
