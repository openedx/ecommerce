define([
        'utils/utils'
    ],
    function (Utils) {
        'use strict';

        describe('stripTimezone', function () {
            it('should return the input value if the input is empty', function () {
                expect(Utils.stripTimezone('')).toEqual('');
                expect(Utils.stripTimezone(null)).toBeNull();
                expect(Utils.stripTimezone(undefined)).toBeUndefined();
            });

            it('should return the datetime without the timezone component', function () {
                var dt = '2015-01-01T00:00:00';
                expect(Utils.stripTimezone(dt + 'Z')).toEqual(dt);
            });
        });

        describe('restoreTimezone', function () {
            it('should return the input value if the input is empty', function () {
                expect(Utils.restoreTimezone('')).toEqual('');
                expect(Utils.restoreTimezone(null)).toBeNull();
                expect(Utils.restoreTimezone(undefined)).toBeUndefined();
            });

            it('should return the datetime with the timezone component', function () {
                var dt = '2015-01-01T00:00:00';
                expect(Utils.restoreTimezone(dt)).toEqual(dt + '+00:00');
            });
        });
    }
);
