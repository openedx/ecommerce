define(['underscore'], function (_) {
    'use strict';

    var utils = {
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
        }
    };

    return utils;
});
