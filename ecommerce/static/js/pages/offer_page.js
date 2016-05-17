define([
        'routers/offer_router',
        'views/offer_view',
        'pages/page',
        'collections/offer_collection'
    ],
    function (OfferRouter,
              OfferView,
              Page,
              OfferCollection) {
        'use strict';

        return Page.extend({
            title: gettext('Redeem'),

            initialize: function(options) {
                this.collection = new OfferCollection({code: options.code});
                this.view = new OfferView({code: options.code, collection: this.collection});
                this.listenTo(this.collection, 'update', this.refresh);
                this.collection.fetch();
            }
        });
    }
);
