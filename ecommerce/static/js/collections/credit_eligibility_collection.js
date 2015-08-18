define([
        'backbone',
        'underscore.string',
        'models/credit_eligibility_model'
    ],
    function (Backbone,
              _s,
              CreditEligibility) {
        'use strict';

        return Backbone.Collection.extend({
                model: CreditEligibility,

                /**
                 * Initializes the collection.
                 *
                 * @param {Object} options This Object MUST contain lmsRootUrl, username, and courseKey keys.
                 */
                initialize: function (options) {
                    this.lmsRootUrl = options.lmsRootUrl;
                    this.username = options.username;
                    this.courseKey = options.courseKey;
                },

                /**
                 * Returns the URL where eligibility data should be retrieved.
                 * @returns {String}
                 */
                url: function () {
                    var data = {
                        root: this.lmsRootUrl,
                        username: encodeURIComponent(this.username),
                        courseKey: encodeURIComponent(this.courseKey)
                    };

                    return _s.sprintf(
                        '%(root)s/api/credit/v1/eligibility/?username=%(username)s&course_key=%(courseKey)s',
                        data
                    );
                }
            }
        );
    }
);
