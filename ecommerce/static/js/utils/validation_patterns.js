define([
    'backbone',
    'backbone.validation',
    'underscore'
],
    function(
        Backbone,
        BackboneValidation,
        _) {
        'use strict';

        // Add custom validation patterns to Backbone.Validation
        _.extend(Backbone.Validation.patterns, {
            courseId: /[^/+]+(\/|\+)[^/+]+(\/|\+)[^/]+/
        });

        _.extend(Backbone.Validation.messages, {
            courseId: gettext('The course ID is invalid.')
        });

        _.extend(Backbone.Validation.patterns, {
            productName: /^((?!&\w+;|<\/*\w+>).)*$/
        });

        _.extend(Backbone.Validation.messages, {
            productName: gettext('The product name cannot contain HTML.')
        });

        _.extend(Backbone.Validation.patterns, {
            sales_force_id: /^006[a-zA-Z0-9]{15}$|^none$/
        });

        _.extend(Backbone.Validation.messages, {
            sales_force_id: gettext('Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006')
        });

        _.extend(Backbone.Validation.patterns, {
            salesforce_opportunity_line_item: /^[0-9]{1}[a-zA-Z0-9]{17}$|^none$/
        });

        _.extend(Backbone.Validation.messages, {
            salesforce_opportunity_line_item: gettext(
                'Salesforce Opportunity Line Item must be 18 alphanumeric characters and begin with a number'
                )
        });
    }
);
