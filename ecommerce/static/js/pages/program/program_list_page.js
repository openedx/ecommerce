define([
        'collections/program_collection',
        'views/program/program_list_view',
        'pages/page'
    ],
    function (ProgramCollection,
              ProgramListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Programs'),

            initialize: function () {
                this.collection = new ProgramCollection();
                this.view = new ProgramListView({collection: this.collection});
                this.render();
                this.collection.fetch({remove: false, data: {page_size: 50}});
            }
        });
    }
);
