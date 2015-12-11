require([
        'jquery',
        'backbone',
        'backbone.validation',
        'bootstrap',
        'bootstrap_accessibility',
        'underscore'
    ],
    function () {
        'use strict';

        $(function () {
            // Activate all pre-rendered tooltips.
            $('[data-toggle="tooltip"]').tooltip();
        });

        // NOTE (CCB): Even if validation fails, force the model to be updated. This will ensure calls
        // to model.isValid(true) return false when we validate models before saving. Without forceUpdate,
        // our models would always be valid, and we'd have to add additional code to check the form fields
        // before saving.
        Backbone.Validation.configure({
            forceUpdate: true,
            labelFormatter: 'label'
        });
    }
);
