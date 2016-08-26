define([
        'jquery',
        'underscore',
        'underscore.string',
        'collections/course_collection',
        'models/course_model',
        'views/dynamic_catalog_view'
    ],
    function ($,
              _,
              _s,
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
                    seat_types: ['verified', 'professional']
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
                var course_key = 'a/b/c',
                    certificate_type = 'verified',
                    seat = {
                    'title': 'Seat in ABC Course',
                    'attribute_values': [{
                        'name': 'course_key',
                        'value': course_key
                    }, {
                        'name': 'certificate_type',
                        'value': certificate_type
                    }
                    ]
                },
                row_data = view.getRowData(seat);

                expect(row_data).toEqual({
                    'id': course_key,
                    'name': seat.title,
                    'type': _s(certificate_type).capitalize().value()
                });
            });

            it('should call Course Catalog API if previewCatalog was called and create a datatable', function () {
                var args,
                    calls,
                    e = $.Event('click');

                spyOn(e, 'preventDefault');
                spyOn(Backbone, 'ajax');
                spyOn($.prototype, 'DataTable').and.callThrough();
                view.previewCatalog(e);

                expect(e.preventDefault).toHaveBeenCalled();
                expect(Backbone.ajax).toHaveBeenCalled();
                expect($.prototype.DataTable).toHaveBeenCalled();

                args = $.prototype.DataTable.calls.argsFor(0)[0];
                expect(args.autoWidth).toBeFalsy();
                expect(args.destroy).toBeTruthy();
                expect(args.info).toBeTruthy();
                expect(args.paging).toBeTruthy();
                expect(args.ordering).toBeFalsy();
                expect(args.searching).toBeFalsy();
                expect(args.columns).toEqual([
                    {
                        title: 'Course ID', data: 'id',
                        sTitle: 'Course ID', mData: 'id'
                    },
                    {
                        title: 'Seat title', data: 'name',
                        sTitle: 'Seat title', mData: 'name',
                    },
                    {
                        title: 'Seat type', data: 'type',
                        sTitle: 'Seat type', mData: 'type',
                    }
                ]);

                calls = Backbone.ajax.calls;
                args = calls.argsFor(calls.count() - 1)[0];
                expect(args.type).toEqual('GET');
                expect(args.url).toEqual(window.location.origin + '/api/v2/catalogs/preview/');
                expect(args.data).toEqual(
                    {query: view.query, seat_types: view.seat_types.join(), limit: 10, offset: 0}
                );
                expect(args.success).toEqual(view.onSuccess);
            });

            it('should fill datatable on successful AJAX call to Course Catalog API', function () {
                var API_data = {
                    'next': 'test.link',
                    'seats': [{
                        'title': 'Seat in ABC Course',
                        'attribute_values': [{
                            'name': 'course_key',
                            'value': 'a/b/c'
                        }, {
                            'name': 'certificate_type',
                            'value': 'verified'
                        }
                        ]
                    },{
                        'title': 'Seat in DEF Course',
                        'attribute_values': [{
                            'name': 'course_key',
                            'value': 'd/e/f'
                        }, {
                            'name': 'certificate_type',
                            'value': 'professional'
                        }
                        ]
                    }]
                };
                view.previewCatalog($.Event('click'));
                this.table = view.$('#seatsTable').DataTable();
                _.bind(view.onSuccess, this);
                spyOn(window, 'setTimeout');

                view.onSuccess(API_data);
                expect(window.setTimeout).toHaveBeenCalled();
                expect(this.table.row(0).data()).toEqual(view.getRowData(API_data.seats[0]));
                expect(this.table.row(1).data()).toEqual(view.getRowData(API_data.seats[1]));
            });

            it('should call stopEventPropagation when disabled or active button pressed', function () {
                var e = $.Event('click');
                view.$el.append('<div class="pagination">' +
                    '<li class="paginate_button previous disabled">' +
                    '<a href="#">Previous</a>' +
                    '</li></div>');

                spyOn(e, 'stopPropagation');
                view.stopEventPropagation(e);
                expect(e.stopPropagation).toHaveBeenCalled();

                spyOn(view, 'stopEventPropagation');
                view.delegateEvents();
                view.$('.pagination .disabled').trigger('click');
                expect(view.stopEventPropagation).toHaveBeenCalled();
            });
        });
    }
);
