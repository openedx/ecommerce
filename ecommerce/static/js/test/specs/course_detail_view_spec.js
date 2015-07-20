define([
        'jquery',
        'underscore.string',
        'models/course_model',
        'views/course_detail_view'
       ],
       function ($, _s, CourseModel, CourseDetailView) {

           describe('course list view', function () {

                var view,
                    model,
                    renderInterval,
                    COURSE_ID = 'edX/DemoX.1/2014';

                beforeEach(function (done) {

                    model = new CourseModel();

                    spyOn(collection, 'fetch').and.callFake(function () {
                        model.set({

                        })
                    });

                    // Set up the environment
                    setFixtures(_s.sprintf('<div class="course-detail-view" data-course-id="%s"></div>', COURSE_ID));

                    view = new CourseDetailView();

                    // Wait till the DOM is rendered before continuing
                    renderInterval = setInterval(function () {
                        if (view.$el.html()) {
                            clearInterval(renderInterval);
                            done();
                        }
                    }, 100);

                });

                it('should change the default filter placeholder to a custom string', function () {
                    expect(view.$el.find('#courseTable_filter input').attr('placeholder')).toBe('Filter by org or course ID');
                });

                it('should adjust the style of the filter textbox', function () {

                    var $tableInput = view.$el.find('#courseTable_filter input');

                    expect($tableInput.hasClass('field-input input-text')).toBeTruthy();
                    expect($tableInput.hasClass('form-control input-sm')).toBeFalsy();

                });

                it('should populate the table based on the course collection', function () {

                    var table = $('#courseTable').DataTable();
                        tableData = table.data();

                        expect(tableData.data().length).toBe(collection.length);

                });

            });
    }
);
