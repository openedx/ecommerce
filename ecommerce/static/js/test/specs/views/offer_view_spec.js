define([
        'jquery',
        'underscore',
        'models/offer_model',
        'views/offer_view',
        'collections/offer_collection'
    ],
    function ($,
              _,
              OfferModel,
              OfferView,
              OfferCollection) {
        'use strict';

        describe('offer view', function() {
            var view,
                collection,
                code,
                course = new OfferModel({
                    benefit: {
                        type: 'Percentage',
                        value: 100
                    },
                    stockrecords: {
                        id: 2,
                        product: 3,
                        partner: 1,
                        partner_sku: '8CF08E5',
                        price_currency: 'USD',
                        price_excl_tax: '100.00'
                    },
                    image_url: 'img/src/url',
                    seat_type: 'Not verified',
                    organization: 'edX',
                    title: 'edX Demonstration Course',
                    course_start_date: '2013-02-05T05:00:00Z',
                    id: 'course-v1:edX+DemoX+Demo_Course',
                    voucher_end_date: '2016-07-29T00:00:00Z',
                    contains_verified: true,
                }),
                course2 = new OfferModel({
                    benefit: {
                        type: 'Not percentage',
                        value: 20
                    },
                    stockrecords: {
                        id: 2,
                        product: 3,
                        partner: 1,
                        partner_sku: '8CF08E5',
                        price_currency: 'USD',
                        price_excl_tax: '100.00'
                    },
                    image_url: 'img/src/url2',
                    seat_type: 'verified',
                    organization: 'edX',
                    title: 'edX Demonstration Course',
                    course_start_date: '2013-02-05T05:00:00Z',
                    id: 'course-v1:edX+DemoX+Demo_Courseewewe',
                    voucher_end_date: '2016-07-29T00:00:00Z',
                    contains_verified: true,
                });

            beforeEach(function() {
                $('body').append('<div class="verified-info"></div>');
                code = 'ABCDE';
                collection = new OfferCollection(null, {code: code});
                collection.add([ course, course2 ]);
                view = new OfferView({code: code, collection: collection}).render();
            });

            it('should show the verified certificate info', function() {
                expect($('.verified-info').hasClass('hidden')).toBeFalsy();
            });

            it('should hide the verified certificate info', function() {
                view.collection.at(0).set('contains_verified', false);
                view.showVerifiedCertificate();
                expect($('.verified-info').hasClass('hidden')).toBeTruthy();
            });

            it('should call functions when formatValues called with course', function() {
                spyOn(view, 'setNewPrice');
                spyOn(view, 'formatBenefitValue');
                spyOn(view, 'formatDate');
                view.formatValues(course);
                expect(view.setNewPrice).toHaveBeenCalledWith(course);
                expect(view.formatBenefitValue).toHaveBeenCalledWith(course);
                expect(view.formatDate).toHaveBeenCalledWith(course);
            });

            it('should call functions when refreshData called', function() {
                spyOn(_, 'each');
                view.refreshData();
                expect(_.each).toHaveBeenCalledWith(view.collection.models, view.formatValues, view);
            });

            it('should format dates when formatDate called', function() {
                view.formatDate(view.collection.models[0]);
                expect(view.collection.models[0].get('course_start_date_text')).toBe('Course starts: Feb 05, 2013');
                expect(view.collection.models[0].get('voucher_end_date_text')
                ).toBe('Discount valid until Jul 29, 2016');
            });

            it('should set new price when setNewPrice called', function() {
                view.setNewPrice(view.collection.models[0]);
                expect(view.collection.models[0].get('new_price')).toBe('0.00');
                view.setNewPrice(view.collection.models[1]);
                expect(view.collection.models[1].get('new_price')).toBe('80.00');
            });

            it('should set benefit value when formatBenefitValue called', function() {
                view.formatBenefitValue(view.collection.models[0]);
                expect(view.collection.models[0].get('benefit_value')).toBe('100%');
                view.formatBenefitValue(view.collection.models[1]);
                expect(view.collection.models[1].get('benefit_value')).toBe('$20');
            });

            it('should return is seat type verified when checkVerified called', function() {
                expect(view.checkVerified(view.collection.models[0])).toBeTruthy();
                expect(view.checkVerified(view.collection.models[1])).toBeFalsy();
            });

            it('should set isEnrollmentCode when refreshData called', function() {
                view.refreshData();
                expect(view.isEnrollmentCode).toBeTruthy();
            });

            it('should call refreshData and renderPagination when render called', function() {
                spyOn(view, 'refreshData');
                spyOn(view, 'renderPagination');
                view.render();
                expect(view.refreshData).toHaveBeenCalled();
                expect(view.renderPagination).toHaveBeenCalled();
            });

            it('should fetch the page that is selected', function() {
                var ev = $.Event('click');
                ev.target = '<div>1</div>';
                spyOn(view.collection, 'goToPage');

                view.goToPage(ev);
                expect(view.collection.page).toBe(1);
                expect(view.collection.goToPage).toHaveBeenCalled();
            });

            it('should fetch the previous page of results', function() {
                spyOn(view.collection, 'previousPage');
                view.previous();
                expect(view.collection.previousPage).toHaveBeenCalled();
            });

            it('should create list item', function() {
                var value = view.createListItem(1, false),
                    string = '<li class="page-item">' +
                    '<button aria-label="Load the records for page 1" class="page-number page-link"><span>' +
                    '1</span></button></li>';
                expect(value).toBe(string);
            });

            it('should create ellipsis item', function() {
                var value = view.createEllipsisItem(),
                    string = '<li class="page-item disabled">' +
                    '<button aria-label="Ellipsis" class="page-number page-link disabled"><span>' +
                    '&hellip;</span></button</li>';
                expect(value).toBe(string);
            });

            it('should create previous item', function() {
                var value = view.createPreviousItem(),
                    string = '<li class="page-item">' +
                    '<button aria-label="Load the records for the previous page" class="prev page-link"><span>' +
                    '&laquo;</span></button></li>';
                expect(value).toBe(string);
            });

            it('should create next item', function() {
                var value = view.createNextItem(),
                    string = '<li class="page-item">' +
                    '<button aria-label="Load the records for the next page" class="next page-link"><span>' +
                    '&raquo;</span></button></li>';
                expect(value).toBe(string);
            });

            it('should render pagination correct in all cases', function() {
                var ellipsisSpyCounter = 1;

                spyOn(view, 'createEllipsisItem');
                spyOn(view, 'createPreviousItem');
                spyOn(view, 'createNextItem');
                spyOn(view, 'createListItem');

                collection.numberOfPages = 10;
                collection.perPage = 1;

                for (var i=1; i<=collection.numberOfPages; i++) {
                    collection.page = i;
                    view.renderPagination();

                    expect(view.createPreviousItem).toHaveBeenCalled();
                    expect(view.createNextItem).toHaveBeenCalled();
                    if (collection.page - 4 >= 1 && collection.page + 4 <= collection.numberOfPages) {
                        expect(view.createEllipsisItem.calls.count()).toBe(ellipsisSpyCounter+1);
                        ellipsisSpyCounter += 2;
                    }else {
                        expect(view.createEllipsisItem.calls.count()).toBe(ellipsisSpyCounter);
                        ++ellipsisSpyCounter;
                    }
                    expect(view.createListItem).toHaveBeenCalledWith(collection.page, true);
                }
            });

            it('should work for previous and next', function() {
                spyOn(view, 'createPreviousItem');
                spyOn(view, 'createNextItem');

                collection.page = 1;
                collection.numberOfPages = 5;
                view.renderPagination();

                expect(view.createPreviousItem).toHaveBeenCalledWith(true);
                expect(view.createNextItem).toHaveBeenCalledWith(false);

                collection.page = 5;
                collection.numberOfPages = 5;
                view.renderPagination();

                expect(view.createPreviousItem).toHaveBeenCalledWith(false);
                expect(view.createNextItem).toHaveBeenCalledWith(true);
            });

            it('should get next page from the collection', function() {
                var next_collection_page = {'1': 1, '2': 2};
                spyOn(view.collection, 'nextPage').and.returnValue(next_collection_page);
                spyOn(view, 'changePage');
                view.next();
                expect(view.collection.nextPage).toHaveBeenCalled();
                expect(view.page).toEqual(next_collection_page);
                expect(view.changePage).toHaveBeenCalled();
            });

            it('should get previous page from the collection', function() {
                var previous_collection_page = {'1': 1, '2': 2};
                spyOn(view.collection, 'previousPage').and.returnValue(previous_collection_page);
                spyOn(view, 'changePage');
                view.previous();
                expect(view.collection.previousPage).toHaveBeenCalled();
                expect(view.page).toEqual(previous_collection_page);
                expect(view.changePage).toHaveBeenCalled();
            });

            it('should call showEmptyOfferErrorMessage when a collection is empty and populated.', function() {
                spyOn(view, 'showEmptyOfferErrorMessage').and.callThrough();
                collection.reset();
                collection.populated = true;
                view.render();
                expect(view.showEmptyOfferErrorMessage).toHaveBeenCalled();
            });
        });
    }
);
