define([
        'views/enrollment_code_list_view',
        'pages/page'
    ],
    function (EnrollmentCodeListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Enrollment Codes'),

            initialize: function () {
                this.view = new EnrollmentCodeListView();
                this.render();
            }
        });
    }
);
