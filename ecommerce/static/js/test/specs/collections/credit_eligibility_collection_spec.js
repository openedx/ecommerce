define([
        'collections/credit_eligibility_collection'
    ],
    function (CreditEligibilityCollection) {
        'use strict';

        var collection,
            lmsRootUrl = 'http://lms.local',
            username = 'testuser',
            courseKey = 'course-v1:LinuxFoundationX+LFS101x.2+1T2015';

        beforeEach(function () {
            collection = new CreditEligibilityCollection({
                lmsRootUrl: lmsRootUrl,
                username: username,
                courseKey: courseKey
            });
        });

        describe('CreditEligibilityCollection', function () {
            describe('initialize', function () {
                it('stores lmsRootUrl', function () {
                    expect(collection.lmsRootUrl).toEqual(lmsRootUrl);
                });

                it('stores username', function () {
                    expect(collection.username).toEqual(username);
                });

                it('stores courseKey', function () {
                    expect(collection.courseKey).toEqual(courseKey);
                });
            });

            describe('url', function () {
                it('returns a Credit API URL', function () {
                    var expected = lmsRootUrl + '/api/credit/v1/eligibility/?username=' +
                        username + '&course_key=' + encodeURIComponent(courseKey);
                    expect(collection.url()).toEqual(expected);
                });
            });
        });
    }
);
