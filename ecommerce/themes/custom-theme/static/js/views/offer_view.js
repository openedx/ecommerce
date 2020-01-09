define([
    'jquery',
    'backbone',
    'underscore',
    'underscore.string',
    'moment',
    'text!templates/_offer_course_list.html',
    'text!templates/_offer_error.html'
],
    function($,
              Backbone,
              _,
              _s,
              moment,
              OfferCourseListTemplate,
              OfferErrorTemplate) {
        'use strict';

        return Backbone.View.extend({
            template: _.template(OfferCourseListTemplate),
            errorTemplate: _.template(OfferErrorTemplate),

            events: {
                'click .prev': 'previous',
                'click .next': 'next',
                'click .page-number': 'goToPage'
            },

            initialize: function(options) {
                this.listenTo(this.collection, 'sync', this.render);
                this.code = options.code;
            },

            changePage: function() {
                this.$el.html(
                    this.template({
                        code: this.code,
                        pageHeading: this.$el.closest('#offerApp').data('offerAppPageHeading'),
                        pageHeadingMessage: this.$el.closest('#offerApp').data('offerAppPageHeadingMessage'),
                        courses: this.collection,
                        isCredit: this.isCredit,
                        isEnrollmentCode: this.isEnrollmentCode,
                        page: this.page
                    })
                );
                this.renderPagination();
                this.delegateEvents();
            },

            render: function() {
                if (this.collection.populated && this.collection.length === 0) {
                    this.showEmptyOfferErrorMessage();
                } else if (this.collection.length > 0) {
                    this.showVerifiedCertificate();
                    this.refreshData();
                    this.$el.html(
                        this.template({
                            code: this.code,
                            pageHeading: this.$el.closest('#offerApp').data('offerAppPageHeading'),
                            pageHeadingMessage: this.$el.closest('#offerApp').data('offerAppPageHeadingMessage'),
                            courses: this.collection,
                            isCredit: this.isCredit,
                            isEnrollmentCode: this.isEnrollmentCode,
                            page: this.collection.goToPage(this.collection.page)
                        })
                    );
                    this.renderPagination();
                    this.delegateEvents();
                }
                return this;
            },

            showEmptyOfferErrorMessage: function() {
                this.$el.html(this.errorTemplate(
                    {error_msg: 'This coupon is not valid for any currently available course seats.'}
                ));
            },

            refreshData: function() {
                var benefitData = this.collection.at(0).get('benefit');

                this.isEnrollmentCode = benefitData.type === 'Percentage' && Math.round(benefitData.value) === 100;
                _.each(this.collection.models, this.formatValues, this);

                this.isCredit = this.collection.at(0).get('seat_type') === 'credit';
            },

            checkVerified: function(course) {
                return (course.get('seat_type') !== 'verified');
            },

            formatBenefitValue: function(course) {
                var benefit = course.get('benefit'),
                    benefitValue = Math.round(benefit.value);
                if (benefit.type === 'Percentage') {
                    benefitValue += '%';
                } else {
                    benefitValue = '$' + benefitValue;
                }

                course.set({benefit_value: benefitValue});
            },

            formatDate: function(course) {
                var courseStartDateText = gettext(_s.sprintf('Course starts: %s',
                        moment(course.get('course_start_date')).format('MMM DD, YYYY'))),
                    voucherEndDateText = gettext(_s.sprintf('Discount valid until %s',
                        moment(course.get('voucher_end_date')).format('MMM DD, YYYY')));

                course.set({
                    course_start_date_text: courseStartDateText,
                    voucher_end_date_text: voucherEndDateText
                });
            },

            formatValues: function(course) {
                this.setNewPrice(course);
                this.formatBenefitValue(course);
                this.formatDate(course);
            },

            setNewPrice: function(course) {
                var benefit = course.get('benefit'),
                    newPrice,
                    price;

                if (course.get('seat_type') === 'credit' && !course.multiple_credit_providers) {
                    price = parseFloat(course.get('credit_provider_price')).toFixed(2);
                } else {
                    price = parseFloat(course.get('stockrecords').price_excl_tax).toFixed(2);
                }

                if (benefit.type === 'Percentage') {
                    newPrice = price - (price * (benefit.value / 100));
                } else {
                    newPrice = price - benefit.value;
                    if (newPrice < 0) {
                        newPrice = 0;
                    }
                }

                // eslint-disable-next-line no-param-reassign
                course.get('stockrecords').price_excl_tax = price;
                course.set({new_price: newPrice.toFixed(2)});
            },

            showVerifiedCertificate: function() {
                if (this.collection.at(0).get('contains_verified')) {
                    $('.verified-info').removeClass('hidden');
                } else {
                    $('.verified-info').addClass('hidden');
                }
            },

            /*
            Pagination-related functions
            */
            renderPagination: function() {
                var numberOfPages = this.collection.numberOfPages,
                    frontSpace = 2,
                    showEllipsisAfterRange = 4,
                    showEllipsisBeforeRange = 3;
                this.pagination = this.$('.pagination');
                this.pagination.append(this.createPreviousItem(this.collection.onFirstPage()));

                if (this.collection.page > frontSpace) {
                    this.pagination.append(this.createListItem(1, false));
                    if (this.collection.page === showEllipsisAfterRange) {
                        this.pagination.append(this.createListItem(2, false));
                    } else if (this.collection.page > showEllipsisAfterRange) {
                        this.pagination.append(this.createEllipsisItem());
                    }
                }

                if (this.collection.page > 1) {
                    this.pagination.append(this.createListItem(this.collection.page - 1, false));
                }

                this.pagination.append(this.createListItem(this.collection.page, true));

                if (this.collection.page < numberOfPages) {
                    this.pagination.append(this.createListItem(this.collection.page + 1, false));
                }

                if (this.collection.page + 1 < numberOfPages) {
                    if (this.collection.page === numberOfPages - showEllipsisBeforeRange) {
                        this.pagination.append(this.createListItem(numberOfPages - 1, false));
                    } else if (this.collection.page < numberOfPages - showEllipsisBeforeRange) {
                        this.pagination.append(this.createEllipsisItem());
                    }
                    this.pagination.append(this.createListItem(numberOfPages, false));
                }

                this.pagination.append(this.createNextItem(this.collection.onLastPage()));
            },

            createEllipsisItem: function() {
                var ariaLabelText = gettext('Ellipsis');
                return _s.sprintf('<li class="page-item disabled">' +
                    '<button aria-label="%s" class="page-number page-link disabled"><span>' +
                    '&hellip;</span></button</li>', ariaLabelText);
            },

            createListItem: function(pageNumber, isActive) {
                var ariaLabelText = gettext('Load the records for page ' + pageNumber);
                return _s.sprintf('<li class="page-item%s">' +
                    '<button aria-label="%s" class="page-number page-link"><span>' +
                    '%s</span></button></li>', isActive ? ' active' : '', ariaLabelText, pageNumber);
            },

            createNextItem: function(next) {
                var ariaLabelText = gettext('Load the records for the next page'),
                    disabled = next ? ' disabled' : '';
                return _s.sprintf('<li class="page-item%s">' +
                    '<button aria-label="%s" class="next page-link%s"><span>' +
                    '&raquo;</span></button></li>', disabled, ariaLabelText, disabled);
            },

            createPreviousItem: function(previous) {
                var ariaLabelText = gettext('Load the records for the previous page'),
                    disabled = previous ? ' disabled' : '';
                return _s.sprintf('<li class="page-item%s">' +
                    '<button aria-label="%s" class="prev page-link%s"><span>' +
                    '&laquo;</span></button></li>', disabled, ariaLabelText, disabled);
            },

            goToPage: function(ev) {
                var pageNumber = parseInt($(ev.target).text(), 10);
                this.page = this.collection.goToPage(pageNumber);
                this.changePage();
            },

            next: function() {
                var isNextAvailable = this.collection.nextPage();
                if (isNextAvailable) {
                    this.page = isNextAvailable;
                    this.changePage();
                }
            },

            previous: function() {
                var isPreviousAvailable = this.collection.previousPage();
                if (isPreviousAvailable) {
                    this.page = isPreviousAvailable;
                    this.changePage();
                }
            }
        });
    }
);
