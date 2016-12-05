define([
        'collections/offer_collection',
        'backbone.super'
    ],
    function(OfferCollection) {
        'use strict';
        var collection,
            response = {
                count: 4,
                page: 1,
                next: null,
                previous: null,
                results: [
                    {
                        id: 'edX/DemoX/Demo_Course',
                        url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/',
                        name: 'edX Demonstration Course',
                        verification_deadline: null,
                        type: 'credit',
                        products_url: 'http://ecommerce.local:8002/api/v2/courses/edX/DemoX/Demo_Course/products/',
                        last_edited: '2015-07-28T18:08:15Z'
                    }
                ]
            };

        describe('Offer collection', function() {
            beforeEach(function() {
                collection = new OfferCollection();
            });

            it('should return the results list in the response', function() {
                expect(collection.parse(response)).toEqual(response.results);
            });

            it('should set collection to be populated after it is populated', function() {
                collection.parse(response);
                expect(collection.populated).toBeTruthy();
            });

            it('should fetch the next page.', function() {
                var test_url = 'example.com';
                response.next = test_url;
                spyOn(collection, 'fetch');

                collection.parse(response);
                expect(collection.fetch).toHaveBeenCalled();
                expect(collection.url).toBe(test_url);
            });

            it('should fetch the next page of results', function() {
                spyOn(collection, 'goToPage');
                collection.page = 1;
                collection.total = 8;
                collection.perPage = 4;

                collection.nextPage();
                expect(collection.goToPage).toHaveBeenCalledWith(2);
            });

            it('should not fetch the next page of results', function() {
                spyOn(collection, 'fetch');
                collection.page = 2;
                collection.numberOfPages = 2;
                collection.perPage = 4;

                response = collection.nextPage();
                expect(response).toBeFalsy();
            });

            it('should fetch the previous page of results', function() {
                spyOn(collection, 'goToPage');
                collection.page = 2;
                collection.numberOfPages = 8;
                collection.perPage = 4;

                collection.previousPage();
                expect(collection.goToPage).toHaveBeenCalledWith(1);
            });

            it('should not fetch the previous page of results', function() {
                spyOn(collection, 'fetch');
                collection.page = 1;
                collection.total = 8;
                collection.perPage = 4;

                response = collection.previousPage();
                expect(response).toBeFalsy();
            });

            it('should fetch the page that is selected', function() {
                spyOn(collection, 'updateLimits');

                collection.goToPage(1);
                expect(collection.page).toBe(1);
                expect(collection.updateLimits).toHaveBeenCalled();
            });

            it('should update upperLimit value to collection length on last pagination page', function() {
                spyOn(collection, 'onLastPage').and.returnValue(true);
                collection.length = 8;
                collection.upperLimit = undefined;
                collection.updateLimits();
                expect(collection.upperLimit).toBe(collection.length);
            });
        });
    }
);
