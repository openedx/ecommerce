require([
        'backbone',
        'collections/course_collection',
        'models/course_model',
        'views/course_create_edit_view',
        'views/course_detail_view',
        'views/course_list_view'
    ],
    function (Backbone,
              CourseCollection,
              Course,
              CourseCreateEditView,
              CourseDetailView,
              CourseListView) {
        'use strict';

        var $app,
            courseApp = new (Backbone.Router.extend({
                currentView: null,
                root: '/courses/',

                routes: {
                    '(/)': 'index',
                    'new(/)': 'new',
                    '*path': 'notFound'
                },

                initialize: function () {
                    var courseIdRegex = /([^/+]+(\/|\+)[^/+]+(\/|\+)[^/]+)/;
                    this.route(new RegExp('^' + courseIdRegex.source + '(\/)?$'), 'show');
                    this.route(new RegExp('^' + courseIdRegex.source + '/edit(\/)?$'), 'edit');
                },

                start: function () {
                    Backbone.history.start({pushState: true, root: this.root});
                },

                navigate: function () {
                    // Clean the current view before rendering a new one.
                    if (this.currentView) {
                        this.currentView.remove();
                        this.currentView = null;
                    }

                    Backbone.Router.prototype.navigate.apply(this, arguments);
                },

                notFound: function (path) {
                    alert(path + ' is invalid.');
                },

                index: function () {
                    var collection = new CourseCollection(),
                        view = new CourseListView({collection: collection});

                    document.title = gettext('Courses');

                    this.currentView = view;
                    collection.fetch({
                        success: function () {
                            view.render();
                        }
                    });
                    $('#app').html(view.el);
                },

                new: function () {
                    document.title = gettext('Create New Course');

                    var model = new Course({}),
                        view = new CourseCreateEditView({model: model});

                    this.currentView = view;
                    view.render();
                    $('#app').html(view.el);
                },

                show: function (id) {
                    var model = Course.findOrCreate({id: id}),
                        view = new CourseDetailView({model: model});

                    this.currentView = view;
                    model.fetch({
                        data: {include_products: true},
                        success: function () {
                            document.title = model.get('name') + ' - ' + gettext('View Course');
                            view.render();
                        }
                    });
                    $('#app').html(view.el);
                },

                edit: function (id) {
                    document.title = gettext('Edit Course');

                    var model = Course.findOrCreate({id: id}),
                        view = new CourseCreateEditView({
                            editing: true,
                            model: model
                        });

                    this.currentView = view;

                    model.fetch({
                        data: {include_products: true},
                        success: function () {
                            document.title = model.get('name') + ' - ' + gettext('Edit Course');
                            view.render();

                            // Activate the tooltips
                            $('[data-toggle="tooltip"]').tooltip();
                        }
                    });
                    $('#app').html(view.el);
                }
            }));

        /**
         * Go to a new page within the Course App.
         *
         * Extends Backbone.View.
         *
         * @param {String} fragment
         */
        Backbone.View.prototype.goTo = function (fragment) {
            courseApp.navigate(fragment, {trigger: true});
        };

        $(function () {
            var navigate = function (event) {
                var url = $(this).attr('href').replace(courseApp.root, '');

                if (event.ctrlKey || event.shiftKey || event.metaKey || event.which == 2) {
                    return true;
                }

                event.preventDefault();

                if (url === Backbone.history.getFragment() && url === '') {
                    // Note: We must call the index directly since Backbone does not
                    // support routing to the same route.
                    courseApp.index();
                } else {
                    courseApp.navigate(url, {trigger: true});
                }
            };

            courseApp.start();

            // Handle internal clicks
            $app = $('#app');
            $app.on('click', 'a', navigate);

            // Handle navbar clicks.
            $('a.navbar-brand').on('click', navigate)
        });
    });
