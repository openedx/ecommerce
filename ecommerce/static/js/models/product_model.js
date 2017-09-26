define([
    'backbone',
    'backbone.relational',
    'backbone.validation',
    'moment',
    'underscore',
    'utils/utils'
],
    function(Backbone,
              BackboneRelational,
              BackboneValidation,
              moment,
              _,
              Utils) {
        'use strict';

        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/products/',
            nestedAttributes: [
                'certificate_type',
                'course_key',
                'id_verification_required',
                'credit_provider',
                'credit_hours'
            ],

            parse: function(response) {
                /* eslint-disable no-param-reassign */
                // Un-nest the attributes
                _.each(response.attribute_values, function(data) {
                    this.nestedAttributes.push(data.name);
                    response[data.name] = data.value;
                }, this);

                delete response.attribute_values;

                // Form fields display date-times in the user's local timezone. We want all
                // times to be displayed in UTC to avoid confusion. Strip the timezone data to workaround the UI
                // deficiencies. We will restore the UTC timezone in toJSON().
                response.expires = Utils.stripTimezone(response.expires);
                /* eslint-enable no-param-reassign */

                return response;
            },

            toJSON: function() {
                var data = _.clone(this.attributes);
                data.attribute_values = [];

                // Re-nest the attributes
                _.each(_.uniq(this.nestedAttributes), function(attribute) {
                    if (this.has(attribute)) {
                        data.attribute_values.push({
                            name: attribute,
                            value: this.get(attribute)
                        });
                    }

                    delete data[attribute];
                }, this);

                // Restore the timezone component, and output the ISO 8601 format expected by the server.
                data.expires = Utils.restoreTimezone(data.expires);

                return data;
            }
        });
    }
);
