define([
        'jquery',
        'underscore',
        'collections/course_collection',
        'models/course_model',
        'views/dynamic_catalog_view'
    ],
    function ($,
              _,
              Courses,
              Course,
              DynamicCatalogView) {
        'use strict';

        describe('dynamic catalog view', function () {
            var view;

            beforeEach(function () {
                view = new DynamicCatalogView({
                    creating_editing: true,
                    query: '*:*',
                    seat_types: 'verified,professional'
                });
                view.render();
            });

            it('should call preview catalog if preview button was clicked', function () {
                spyOn(view, 'previewCatalog');
                view.delegateEvents();
                view.$el.find('[name=preview_catalog]').trigger('click');
                expect(view.previewCatalog).toHaveBeenCalled();
            });

            it('should format row data for dynamic catalog preview', function () {
                var course = Course.findOrCreate({
                        'id': 'a/b/c',
                        'name': 'ABC Course',
                        'type': 'verified'
                    }, {parse: true}),
                    row_data = view.getRowData(course);

                expect(row_data).toEqual({
                    'id': course.get('id'),
                    'name': course.get('name'),
                    'type': 'Verified'
                });
            });

            it('should call Course Catalog API if previewCatalog was called', function () {
                var args,
                    calls,
                    e = $.Event('click');

                spyOn(e, 'preventDefault');
                spyOn(Backbone, 'ajax');
                view.previewCatalog(e);

                expect(e.preventDefault).toHaveBeenCalled();
                expect(Backbone.ajax).toHaveBeenCalled();

                calls = Backbone.ajax.calls;
                args = calls.argsFor(calls.count() - 1)[0];
                expect(args.type).toEqual('GET');
                expect(args.url).toEqual(window.location.origin + '/api/v2/catalogs/preview/');
                expect(args.data).toEqual({query: view.query});
                expect(args.success).toEqual(view.onSuccess);
            });

            it('should fill datatable on successful AJAX call to Course Catalog API', function () {
                var API_data = {
                    results: [{
                        key: 'a/b/c'
                    }, {
                        key: 'd/e/f'
                    }]
                },
                args;

                spyOn(_, 'pluck');
                spyOn($.prototype, 'DataTable');
                view.onSuccess(API_data);

                expect(_.pluck).toHaveBeenCalledWith(API_data.results, 'key');
                expect($.prototype.DataTable).toHaveBeenCalled();

                args = $.prototype.DataTable.calls.argsFor(0)[0];
                expect(args.autoWidth).toBeFalsy();
                expect(args.destroy).toBeTruthy();
                expect(args.info).toBeTruthy();
                expect(args.paging).toBeTruthy();
                expect(args.ordering).toBeFalsy();
                expect(args.searching).toBeFalsy();
                expect(args.columns).toEqual([
                    {title: 'Course ID', data: 'id'},
                    {title: 'Course name', data: 'name'},
                    {title: 'Seat type', data: 'type'}
                ]);
            });

            it('should filter courses by calling filterCourses function', function() {
                var course_keys = ['test1/test1/test1', 'test3/test3/test3'],
                    filtered_courses,
                    seat_types = ['verified'];

                view.courses = new Courses([
                    Course.findOrCreate({id: 'test1/test1/test1', type: 'verified'}),
                    Course.findOrCreate({id: 'test2/test2/test2', type: 'verified'}),
                    Course.findOrCreate({id: 'test3/test3/test3', type: 'professional'})
                ]);
                filtered_courses = view.filterCourses(course_keys, seat_types);

                expect(filtered_courses.length).toEqual(1);
                expect(filtered_courses[0].get('id')).toEqual('test1/test1/test1');
                expect(filtered_courses[0].get('type')).toEqual('verified');
            });
        });
    }
);
