define([
        'backbone',
        'models/credit_eligibility_model'
    ],
    function (Backbone,
              CreditEligibility) {
        'use strict';

        return Backbone.Collection.extend({
                model: CreditEligibility,

                /*jshint undef: false */
                url: lmsRootUrl + '/api/credit/v1/eligibility/',
                /*jshint undef: true */
                setUrl: function (username, courseKey) {
                    this.url += '?username=' + username + '&course_key=' + courseKey;

                }
            }
        );
    }
);

