define([
        'views/enrollment_codes_create_view',
        'pages/page'
    ],
    function (EnrollmentCodesCreateView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Enrollment Code'),

            initialize: function () {
                this.view = new EnrollmentCodesCreateView();
                this.render();
            }
        });
    }
);
