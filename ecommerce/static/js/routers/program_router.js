define([
        'backbone',
        'routers/page_router',
        'pages/program/program_list_page',
        'pages/program/program_create_page'
    ],
    function (Backbone,
              PageRouter,
              ProgramListPage,
              ProgramCreatePage) {
        'use strict';

        return PageRouter.extend({
            // Base/root path of the app
            root: '/programs/',

            routes: {
                '(/)': 'index',
                'new(/)': 'new',
                ':id(/)': 'show',
                ':id/edit(/)': 'edit',
                '*path': 'notFound'
            },

            /**
             * Display a list of all programs in the system.
             */
            index: function () {
                var page = new ProgramListPage();
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display details for a single program.
             * @param {String} id - ID of the program to display.
             */
            show: function (id) {
                var page = new ProgramDetailPage({id: id});
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display a form for creating a new program.
             */
            new: function () {
                var page = new ProgramCreatePage();
                this.currentView = page;
                this.$el.html(page.el);
            },

            /**
             * Display a form for editing an existing program.
             */
            edit: function (id) {
                var page = new ProgramEditPage({id: id});
                this.currentView = page;
                this.$el.html(page.el);
            }
        });
    }
);
