define([
    'backbone',
    'backbone.validation',
    'jquery',
    'moment',
    'pikaday',
    'punycode',
    'underscore'],
    function(Backbone,
             BackboneValidation,
             $,
             moment,
             Pikaday,
             punycode,
             _) {
        'use strict';

        return {
            /**
             * Returns the attributes of a node.
             *
             * @param nodeAttributes Attributes of the node.
             * @param startsWithAndStrip Filters only attributes that start with
             *   this string and strips it off the attribute.
             * @param blackList Exclude attributes in this array of strings.
             * @returns Hash of found attributes.
             */
            getNodeProperties: function(nodeAttributes, startsWithAndStrip, blackList) {
                // fill in defaults
                var blackListReassigned = blackList || [],
                    properties = {},
                    startsWithAndStripReassigned = startsWithAndStrip || '';

                _(_(nodeAttributes.length).range()).each(function(i) {
                    var nodeName = nodeAttributes.item(i).nodeName,
                        strippedName;
                    // filter the attributes to just the ones that start with our
                    // selection and aren't in our blacklist
                    if (nodeName.indexOf(startsWithAndStripReassigned) === 0
                        && !_(blackListReassigned).contains(nodeName)) {
                        // remove the
                        strippedName = nodeName.replace(startsWithAndStripReassigned, '');
                        properties[strippedName] =
                            nodeAttributes.item(i).value;
                    }
                });
                return properties;
            },

            /**
             * Strips the timezone component from a datetime string.
             *
             * Input is assumed to be in UTC timezone. Output datetime is formatted as
             * ISO 8601 without the timezone component.
             *
             * @param {String} datetime - String representing a UTC datetime
             * @returns {String}
             */
            stripTimezone: function(datetime) {
                if (datetime) {
                    return moment.utc(new Date(datetime)).format('YYYY-MM-DDTHH:mm:ss');
                }
                return datetime;
            },

            /**
             * Adds the UTC timezone to a given datetime string.
             *
             * Output is formatted as ISO 8601.
             *
             * @param {String} datetime - String representing a datetime WITHOUT a timezone component
             * @returns {String}
             */
            restoreTimezone: function(datetime) {
                if (datetime) {
                    return moment.utc(datetime + 'Z').format();
                }
                return datetime;
            },

            /**
             * Indicates if all models in the array are valid.
             *
             * Calls isValid() on every model in the array.
             *
             * @param {Backbone.Model[]} models
             * @returns {Boolean} indicates if ALL models are valid.
             */
            areModelsValid: function(models) {
                return _.every(models, function(model) {
                    return model.isValid(true);
                });
            },

            /**
             * Bind the provided view for form validation.
             *
             * @param {Backbone.View} view
             */
            bindValidation: function(view) {
                /* istanbul ignore next */
                Backbone.Validation.bind(view, {
                    // eslint-disable-next-line no-shadow
                    valid: function(view, attr) {
                        var $el = view.$el.find('[name=' + attr + ']'),
                            $group = $el.closest('.form-group'),
                            $helpBlock = $group.find('.help-block:first'),
                            className = 'invalid-' + attr,
                            $msg = $helpBlock.find('.' + className);

                        $msg.remove();

                        $group.removeClass('has-error');
                        $helpBlock.addClass('hidden');
                    },
                    // eslint-disable-next-line no-shadow
                    invalid: function(view, attr, error) {
                        var $el = view.$el.find('[name=' + attr + ']'),
                            $group = $el.closest('.form-group'),
                            $helpBlock = $group.find('.help-block:first'),
                            className = 'invalid-' + attr,
                            $msg = $helpBlock.find('.' + className);

                        if (_.isEqual($msg.length, 0)) {
                            $helpBlock.append('<div class="' + className + '">' + error + '</div>');
                        } else {
                            $msg.html(error);
                        }

                        $group.addClass('has-error');
                        $helpBlock.removeClass('hidden');
                    }
                });
            },

            /**
             * Disables a given element when a given operation is running.
             * @param {jQuery} element the element to be disabled.
             * @param operation the operation during whose duration the
             * element should be disabled. The operation should return
             * a JQuery promise.
             */
            disableElementWhileRunning: function(element, operation) {
                element.addClass('is-disabled').attr('aria-disabled', true);
                return operation().always(function() {
                    element.removeClass('is-disabled').attr('aria-disabled', false);
                });
            },

            /**
             * Adds Pikaday date picker for given element in format required.
             * For now this function is required in coupon_form_view.js and
             * course_form_view.js.
             */
            addDatePicker: function(context) {
                _.each(context.$el.find('.add-pikaday'), function(el) {
                    if (el.getAttribute('datepicker-initialized') !== 'true') {
                        new Pikaday({
                            field: el,
                            format: 'YYYY-MM-DDTHH:mm:ss',
                            defaultDate: context.model.get(el.name),
                            setDefaultDate: true,
                            showTime: true,
                            use24hour: false,
                            autoClose: false
                        });
                        el.setAttribute('datepicker-initialized', 'true');
                    }
                });
            },

            /**
             * Validates given domain/domains.
             * @param {String} domains - String that contains a domain or multiple domains separated by comma.
             * @returns {String} Returns invalid domain or undefined if all domains are valid.
             */
            validateDomains: function(domains) {
                var encodedDomainPart,
                    domainArray = domains.split(','),
                    domainParts,
                    invalidDomain;

                if (_.isEmpty(domainArray[domainArray.length - 1])) {
                    return gettext('Trailing comma not allowed.');
                }

                // Go through domains in the array and if invalid domain detected exit loop and remember domain
                invalidDomain = _.find(domainArray, function(el) {
                    var i = 0;
                    domainParts = el.split('.');

                    /*
                     * Conditions being tested:
                     * - double hyphens are not allowed in domains
                     * - two consecutive dots are not allowed
                     * - domains must contain at least one dot which will make domainPartsLength > 1
                     * - top level domain must be at least two characters long
                     * - hyphens are not allowed in top level domain
                     * - numbers are not allowed in top level domain
                     */
                    if (/--/.test(el) ||
                        /\.\./.test(el) ||
                        domainParts.length < 2 ||
                        domainParts[domainParts.length - 1].length < 2 ||
                        /[-0-9]/.test(domainParts[domainParts.length - 1])) {
                        return true;
                    }

                    for (i; i < domainParts.length; i += 1) {
                        // - non of the domain levels can start or end with a hyphen before encoding
                        if (/^-/.test(domainParts[i]) || /-$/.test(domainParts[i])) {
                            return true;
                        }

                        encodedDomainPart = punycode.toASCII(domainParts[i]);

                        // - all encoded domain levels must match given regex expression
                        if (!/^([a-z0-9-]+)$/.test(encodedDomainPart)) {
                            return true;
                        }
                    }
                    return undefined;
                });

                return invalidDomain;
            },

            /**
             * Redirects the page to the designated path.
             * @param {String} path - The path to which to redirect.
             */
            redirect: function(path) {
                window.location.href = path;
            },

            /**
             * Sets the click event on header mobile menu.
             * The menu items should show/hide on click.
             */
            toogleMobileMenuClickEvent: function() {
                $('#hamburger-button').on('click', function() {
                    $(this).attr('aria-expanded', $(this).attr('aria-expanded') === 'false' ? 'true' : 'false');
                    $('#main-navbar-collapse').toggle();
                });
            }
        };
    }
);
