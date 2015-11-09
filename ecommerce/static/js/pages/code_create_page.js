define([
        'models/code_model',
        'views/code_create_edit_view',
        'pages/page'
    ],
    function (Code,
              CodeCreateEditView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Code'),

            initialize: function () {
                this.model = new Code({});
                this.view = new CodeCreateEditView({model: this.model});
                this.render();
            }
        });
    }
);
