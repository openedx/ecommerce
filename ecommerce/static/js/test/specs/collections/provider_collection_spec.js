define([
        'collections/credit_provider_collection'
    ],
    function (CreditProviderCollection) {
        'use strict';

        var collection,
            lmsRootUrl = 'http://lms.local',
            providerIds = 'ASU,MIT';

        beforeEach(function () {
            collection = new CreditProviderCollection({lmsRootUrl: lmsRootUrl, providerIds: providerIds});
        });

        describe('CreditProviderCollection', function () {
            describe('initialize', function () {
                it('stores lmsRootUrl', function () {
                    expect(collection.lmsRootUrl).toEqual(lmsRootUrl);
                });

                it('stores providerIds', function () {
                    expect(collection.providerIds).toEqual(providerIds);
                });
            });

            describe('url', function () {
                it('returns a Credit API URL', function () {
                    var expected = lmsRootUrl + '/api/credit/v1/providers/?provider_ids=' + providerIds;
                    expect(collection.url()).toEqual(expected);
                });
            });
        });
    }
);
