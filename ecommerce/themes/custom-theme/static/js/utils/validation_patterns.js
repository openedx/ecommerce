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
    }
);
