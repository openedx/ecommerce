define([
    'backbone',
    'jquery',
    'pages/page',
    'utils/utils'
],
    function(Backbone,
             $,
             Page,
             Utils
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

            it('should check if render calls the required functions', function() {
                page = new Page();
                spyOn(page, 'renderTitle');
                spyOn(page, 'renderNestedView');
                spyOn(Utils, 'toogleMobileMenuClickEvent');

                page.render();
                expect(page.renderTitle).toHaveBeenCalled();
                expect(page.renderNestedView).toHaveBeenCalled();
                expect(Utils.toogleMobileMenuClickEvent).toHaveBeenCalled();
            });
        });
    });
