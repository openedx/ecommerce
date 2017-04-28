define([
        'models/program_model',
        'views/program/program_detail_view',
        'pages/page'
    ],
    function (Program,
              ProgramDetailView,
              Page) {
        'use strict';

        return Page.extend({
            title: function () {
                return this.model.get('title') + ' - ' + gettext('View Program');
            },

            initialize: function (options) {
                this.model = Program.findOrCreate({id: options.id});
                this.view = new ProgramDetailView({model: this.model});
                this.listenTo(this.model, 'sync', this.refresh);
                this.model.fetch();
            }
        });
    }
);
