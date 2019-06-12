define([
    'collections/course_collection'
],
    function(CourseCollection) {
        'use strict';

        var collection,
            response = {
                count: 1,
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

        beforeEach(function() {
            collection = new CourseCollection();
        });

        describe('Course collection', function() {
            describe('parse', function() {
                it('should return the results list in the response', function() {
                    expect(collection.parse(response)).toEqual(response.results);
                });

                it('should fetch the next page of results', function() {
                    spyOn(collection, 'fetch').and.returnValue(null);
                    response.next = '/api/v2/courses/?page=2';

                    collection.parse(response);
                    expect(collection.fetch).toHaveBeenCalledWith({remove: false, url: '/api/v2/courses/?page=2'});
                });
            });
        });
    }
);
