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

        describe('offer view', function () {
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
                    voucher_end_date: '2016-07-29T00:00:00Z'
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
                    voucher_end_date: '2016-07-29T00:00:00Z'
                });

            beforeEach(function () {
                code = 'ABCDE';
                collection = new OfferCollection(null, {code: code});
                collection.add([ course, course2 ]);
                view = new OfferView({code: code, collection: collection});
            });

            it('should hide the verified certificate info', function () {
                expect(view.$el.find('.verified-info:hidden')).toBeTruthy();
            });

            it('should call functions when formatValues called with course', function () {
                spyOn(view, 'setNewPrice');
                spyOn(view, 'formatBenefitValue');
                spyOn(view, 'formatDate');
                view.formatValues(course);
                expect(view.setNewPrice).toHaveBeenCalledWith(course);
                expect(view.formatBenefitValue).toHaveBeenCalledWith(course);
                expect(view.formatDate).toHaveBeenCalledWith(course);
            });

            it('should call functions when refreshData called', function () {
                spyOn(view, 'showVerifiedCertificate');
                spyOn(_, 'each');
                view.refreshData();
                expect(view.showVerifiedCertificate).toHaveBeenCalled();
                expect(_.each).toHaveBeenCalledWith(view.collection.models, view.formatValues, view);
            });

            it('should format dates when formatDate called', function () {
                view.formatDate(view.collection.models[0]);
                expect(view.collection.models[0].get('course_start_date_text')).toBe('Course starts: Feb 05, 2013');
                expect(view.collection.models[0].get('voucher_end_date_text')
                ).toBe('Discount valid until Jul 29, 2016');
            });

            it('should set new price when setNewPrice called', function () {
                view.setNewPrice(view.collection.models[0]);
                expect(view.collection.models[0].get('new_price')).toBe(0);
                view.setNewPrice(view.collection.models[1]);
                expect(view.collection.models[1].get('new_price')).toBe(80);
            });

            it('should set benefit value when formatBenefitValue called', function () {
                view.formatBenefitValue(view.collection.models[0]);
                expect(view.collection.models[0].get('benefit_value')).toBe('100%');
                view.formatBenefitValue(view.collection.models[1]);
                expect(view.collection.models[1].get('benefit_value')).toBe('20$');
            });

            it('should return is seat type verified when checkVerified called', function () {
                expect(view.checkVerified(view.collection.models[0])).toBeTruthy();
                expect(view.checkVerified(view.collection.models[1])).toBeFalsy();
            });

            it('should set isEnrollmentCode when refreshData called', function () {
                view.refreshData();
                expect(view.isEnrollmentCode).toBeTruthy();
            });

            it('should call refreshData and renderPagination when render called', function () {
                spyOn(view, 'refreshData');
                spyOn(view, 'renderPagination');
                view.render();
                expect(view.refreshData).toHaveBeenCalled();
                expect(view.renderPagination).toHaveBeenCalled();
            });

            it('should fetch the page that is selected', function () {
                var ev = $.Event('click');
                ev.target = '<div>1</div>';
                spyOn(view.collection, 'fetch');

                view.goToPage(ev);
                expect(view.collection.page).toBe(1);
                expect(view.collection.fetch).toHaveBeenCalled();
            });

            it('should fetch the next page of results', function () {
                spyOn(view.collection, 'fetch');
                view.collection.page = 1;
                view.collection.total = 8;
                view.collection.perPage = 4;

                view.next();
                expect(view.collection.fetch).toHaveBeenCalled();
            });

            it('should fetch the previous page of results', function () {
                spyOn(view.collection, 'fetch');
                view.collection.page = 2;
                view.collection.total = 8;
                view.collection.perPage = 4;

                view.previous();
                expect(view.collection.fetch).toHaveBeenCalled();
            });

            it('should create list item', function () {
                var value = view.createListItem(1, false),
                    string = '<li class="page-item">' +
                    '<button aria-label="Load the records for page 1" class="page-number page-link"><span>' +
                    '1</span></button></li>';
                expect(value).toBe(string);
            });

            it('should create ellipsis item', function () {
                var value = view.createEllipsisItem(),
                    string = '<li class="page-item disabled">' +
                    '<button aria-label="Ellipsis" class="page-number page-link"><span>' +
                    '&hellip;</span></button</li>';
                expect(value).toBe(string);
            });

            it('should create previous item', function () {
                var value = view.createPreviousItem(),
                    string = '<li class="page-item">' +
                    '<button aria-label="Load the records for the previous page" class="prev page-link"><span>' +
                    '&laquo;</span></button></li>';
                expect(value).toBe(string);
            });

            it('should create next item', function () {
                var value = view.createNextItem(),
                    string = '<li class="page-item">' +
                    '<button aria-label="Load the records for the next page" class="next page-link"><span>' +
                    '&raquo;</span></button></li>';
                expect(value).toBe(string);
            });

            it('should render pagination correct in all cases', function () {
                var ellipsisSpyCounter = 1;

                spyOn(view, 'createEllipsisItem');
                spyOn(view, 'createPreviousItem');
                spyOn(view, 'createNextItem');
                spyOn(view, 'createListItem');

                collection.total = 10;
                collection.perPage = 1;

                for (var i=1; i<=collection.total; i++) {
                    collection.page = i;
                    collection.pageInfo();
                    view.renderPagination();

                    expect(view.createPreviousItem).toHaveBeenCalled();
                    expect(view.createNextItem).toHaveBeenCalled();
                    if (collection.page - 4 >= 1 && collection.page + 4 <= collection.total) {
                        expect(view.createEllipsisItem.calls.count()).toBe(ellipsisSpyCounter+1);
                        ellipsisSpyCounter += 2;
                    }else {
                        expect(view.createEllipsisItem.calls.count()).toBe(ellipsisSpyCounter);
                        ++ellipsisSpyCounter;
                    }
                    expect(view.createListItem).toHaveBeenCalledWith(collection.page, true);
                }
            });

            it('should work for previous and next', function () {
                spyOn(view, 'createPreviousItem');
                spyOn(view, 'createNextItem');

                collection.total = 2;
                collection.perPage = 1;
                collection.page = 1;
                collection.next = 'some/link';
                collection.prev = null;
                view.renderPagination();

                expect(view.createPreviousItem).toHaveBeenCalledWith(collection.prev);
                expect(view.createNextItem).toHaveBeenCalledWith(collection.next);

                collection.next = null;
                collection.prev = 'some/link';
                view.renderPagination();

                expect(view.createPreviousItem).toHaveBeenCalledWith(collection.prev);
                expect(view.createNextItem).toHaveBeenCalledWith(collection.next);
            });

        });
    }
);