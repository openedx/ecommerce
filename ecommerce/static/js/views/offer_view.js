define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/_offer_course_list.html'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              OfferCourseListTemplate) {

        'use strict';

        return Backbone.View.extend({
            template: _.template(OfferCourseListTemplate),

            events: {
                'click .prev': 'previous',
                'click .next': 'next',
                'click .page-number': 'goToPage'
            },

            initialize: function(options) {
                this.code = options.code;
            },

            goToPage: function(ev) {
                this.collection.goToPage(ev);
            },

            previous: function() {
                this.collection.previousPage();
            },

            next: function() {
                this.collection.nextPage();
            },

            refreshData: function() {
                this.showVerifiedCertificate();
                this.isEnrollmentCode =
                    this.collection.models[0].get('benefit').type === 'Percentage' &&
                    Math.round(this.collection.models[0].get('benefit').value) === 100;

                _.each(this.collection.models, this.formatValues, this);
            },

            formatValues: function(course) {
                this.setNewPrice(course);
                this.formatBenefitValue(course);
                this.formatDate(course);
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

            setNewPrice: function(course) {
                var benefit = course.get('benefit'),
                    new_price,
                    price = parseFloat(course.get('stockrecords').price_excl_tax).toFixed(2);

                if (benefit.type === 'Percentage') {
                    new_price = price - (price * (benefit.value / 100));
                } else {
                    new_price = price - benefit.value;
                    if (new_price < 0) {
                        new_price = 0;
                    }
                }

                course.get('stockrecords').price_excl_tax = price;
                course.set({new_price: new_price.toFixed(2)});
            },

            formatBenefitValue: function(course) {
                var benefit = course.get('benefit'),
                    benefit_value = Math.round(benefit.value);
                if (benefit.type === 'Percentage') {
                    benefit_value = benefit_value + '%';
                } else {
                    benefit_value = '$' + benefit_value;
                }

                course.set({benefit_value: benefit_value});
            },

            showVerifiedCertificate: function() {
                if (this.collection.models[0].get('contains_verified')) {
                    $('.verified-info').removeClass('hidden');
                } else {
                    $('.verified-info').addClass('hidden');
                }
            },

            checkVerified: function(course) {
                return (course.get('seat_type') !== 'verified');
            },

            render: function() {
                this.refreshData();
                this.$el.html(
                    this.template({
                        courses: this.collection.models,
                        code: this.code,
                        isEnrollmentCode: this.isEnrollmentCode,
                        pageInfo: this.collection.pageInfo()
                    })
                );
                this.renderPagination();
                this.delegateEvents();
                return this;
            },

            createListItem: function(pageNumber, isActive) {
                var ariaLabelText = gettext('Load the records for page ' + pageNumber);
                return _s.sprintf('<li class="page-item%s">' +
                    '<button aria-label="%s" class="page-number page-link"><span>' +
                    '%s</span></button></li>', isActive ? ' active' : '', ariaLabelText, pageNumber);
            },

            createEllipsisItem: function() {
                var ariaLabelText = gettext('Ellipsis');
                return _s.sprintf('<li class="page-item disabled">' +
                    '<button aria-label="%s" class="page-number page-link"><span>' +
                    '&hellip;</span></button</li>', ariaLabelText);
            },

            createPreviousItem: function(previous) {
                var ariaLabelText = gettext('Load the records for the previous page');
                return _s.sprintf('<li class="page-item%s">' +
                    '<button aria-label="%s" class="prev page-link"><span>' +
                    '&laquo;</span></button></li>', previous === null ? ' disabled' : '', ariaLabelText);
            },

            createNextItem: function(next) {
                var ariaLabelText = gettext('Load the records for the next page');
                return _s.sprintf('<li class="page-item%s">' +
                    '<button aria-label="%s" class="next page-link"><span>' +
                    '&raquo;</span></button></li>', next === null ? ' disabled' : '', ariaLabelText);
            },

            renderPagination: function() {
                var numberOfPages = this.collection.numberOfPages(),
                    frontSpace = 2,
                    showEllipsisAfterRange = 4,
                    showEllipsisBeforeRange = 3;
                this.pagination = this.$('.pagination');
                this.pagination.append(this.createPreviousItem(this.collection.prev));

                if (this.collection.page > frontSpace) {
                    this.pagination.append(this.createListItem(1, false));
                    if (this.collection.page === showEllipsisAfterRange) {
                        this.pagination.append(this.createListItem(2, false));
                    } else if (this.collection.page > showEllipsisAfterRange) {
                        this.pagination.append(this.createEllipsisItem());
                    }
                }

                if (this.collection.prev) {
                    this.pagination.append(this.createListItem(this.collection.page - 1, false));
                }

                this.pagination.append(this.createListItem(this.collection.page, true));

                if (this.collection.next) {
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

                this.pagination.append(this.createNextItem(this.collection.next));
            }
        });
    }
);
