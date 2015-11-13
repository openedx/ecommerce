define([
        'models/enrollment_code_model',
        'views/enrollment_code_create_edit_view',
        'pages/page'
    ],
    function (EnrollmentCode,
              EnrollmentCodeCreateEditView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Code'),

            initialize: function () {
                this.model = new EnrollmentCode({});
                this.view = new EnrollmentCodeCreateEditView({model: this.model});
                this.render();
            }
        });
    }
);
