define([
        'models/program_model',
        'views/program/program_create_edit_view',
        'pages/page'
    ],
    function (Program,
              ProgramCreateEditView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Program'),

            initialize: function () {
                this.model = new Program({});
                this.view = new ProgramCreateEditView({model: this.model});
                this.render();
            }
        });
    }
);
