define([
        'moment',
        'underscore'],
    function (moment,
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
            getNodeProperties: function (nodeAttributes, startsWithAndStrip, blackList) {
                var properties = {};

                // fill in defaults
                startsWithAndStrip = startsWithAndStrip || '';
                blackList = blackList || [];

                _(_(nodeAttributes.length).range()).each(function (i) {
                    var nodeName = nodeAttributes.item(i).nodeName,
                        strippedName;
                    // filter the attributes to just the ones that start with our
                    // selection and aren't in our blacklist
                    if (nodeName.indexOf(startsWithAndStrip) === 0 && !_(blackList).contains(nodeName)) {
                        // remove the
                        strippedName = nodeName.replace(startsWithAndStrip, '');
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
            stripTimezone: function (datetime) {
                if (datetime) {
                    datetime = moment.utc(datetime).format('YYYY-MM-DDTHH:mm:ss');
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
            restoreTimezone: function (datetime) {
                if (datetime) {
                    datetime = moment.utc(datetime + 'Z').format();
                }
                return datetime;
            }
        };
    });
