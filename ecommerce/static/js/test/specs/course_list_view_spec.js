define([
        'jquery',
        'views/course_list_view'
       ],
       function ($, CourseListView) {

        describe('course list view', function () {

            var view = {};

            beforeEach(function () {
                view = new CourseListView();

                view.render();
            });

            it('course list view exists', function () {
                console.info(view.$el.html());
                // expect(view.$el.find('#courseTable_filter input').attr('placeholder')).toBe(gettext('Filter by org or course ID'));
                expect(view).toBeDefined();
            });

        });
    }
);
