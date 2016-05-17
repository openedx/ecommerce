define([
        'backbone',
        'models/offer_model',
        'underscore.string'
    ],
    function (Backbone,
              OfferModel,
              _s) {
        'use strict';

        return Backbone.Collection.extend({
            model: OfferModel,
            baseUrl: '/api/v2/vouchers/offers/',

            initialize: function (options) {
                if (options) {
                    this.code = options.code;
                }
                this.page = 1;
                this.perPage = 6;
            },

            parse: function (response) {
                if (response.page) {
                    (this.page = response.page);
                }
                this.total = response.count;
                this.prev = response.previous;
                this.next = response.next;
                return response.results;
            },

            url: function () {
                return _s.sprintf('%s?%s',
                    this.baseUrl,
                    $.param({ code: this.code, page: this.page, page_size: this.perPage })
                );
            },

            pageInfo: function () {
                var info = {
                    total: this.total,
                    page: this.page,
                    perPage: this.perPage,
                    pages: this.numberOfPages(),
                    prev: false,
                    next: false
                    },
                    max = Math.min(this.total, this.page * this.perPage);

                if (this.total === this.pages * this.perPage) {
                    max = this.total;
                }

                info.range = [(this.page - 1) * this.perPage + 1, max];

                if (this.page > 1) {
                    info.prev = this.page - 1;
                }

                if (this.page < info.pages) {
                    info.next = this.page + 1;
                }

                return info;
            },

            numberOfPages: function () {
                return Math.ceil(this.total / this.perPage);
            },

            nextPage: function() {
                if (!this.pageInfo().next) {
                    return false;
                }else {
                    this.page = this.page + 1;
                    return this.fetch();
                }
              },
            previousPage: function() {
                if (!this.pageInfo().prev) {
                    return false;
                }else {
                    this.page = this.page - 1;
                    return this.fetch();
                }
            },
            goToPage: function (ev) {
                this.page = parseInt($(ev.target).text());
                return this.fetch();
            }

        });
    }
);
