define([
        'backbone',
        'jquery',
        'pages/page'
    ],
    function(Backbone,
             $,
             Page
             ) {
        'use strict';

        describe('Base page', function() {
            var page;

            it('should remove and render the view when refresh is called', function() {
                page = new Page();
                page.view = new Backbone.View();
                spyOn(page.view, 'remove');
                spyOn(page, 'render');

                page.refresh();
                expect(page.view.remove).toHaveBeenCalled();
                expect(page.render).toHaveBeenCalled();
            });
        });
});
