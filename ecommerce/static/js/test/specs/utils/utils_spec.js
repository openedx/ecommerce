define([
        'backbone',
        'test/spec-utils',
        'utils/utils',
        'views/coupon_form_view',
        'test/mock_data/categories',
        'ecommerce'
    ],
    function (Backbone,
              SpecUtils,
              Utils,
              CouponFormView,
              Mock_Categories,
              ecommerce) {
        'use strict';

        describe('Utils', function () {
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

            describe('areModelsValid', function () {
                it('should return true if all models are valid', function () {
                    var ModelClass = SpecUtils.getModelForValidation(true),
                        models = [new ModelClass(), new ModelClass()];

                    expect(Utils.areModelsValid(models)).toEqual(true);
                });

                it('should return false if any of the models is NOT valid', function () {
                    var ModelClass = SpecUtils.getModelForValidation(false),
                        models = [new ModelClass(), new ModelClass()];

                    expect(Utils.areModelsValid(models)).toEqual(false);

                    // A mixture of validation statuses should always return false.
                    models.push(new (SpecUtils.getModelForValidation(true))());
                    expect(Utils.areModelsValid(models)).toEqual(false);
                });
            });

            describe('disableElementWhileRunning', function () {

                beforeEach(function () {
                    ecommerce.coupons = {
                        categories: Mock_Categories
                    };
                });

                it('adds "is-disabled" class to element while action is running and removes it after', function() {
                    var ModelClass = SpecUtils.getModelForValidation(false),
                        model = new ModelClass(),
                        view = new CouponFormView({ editing: false, model: model }).render(),
                        button,
                        deferred = new $.Deferred(),
                        promise = deferred.promise();
                    button = view.$el.find('button').first();
                    expect(button).not.toHaveClass('is-disabled');
                    Utils.disableElementWhileRunning(button, function() { return promise; });
                    expect(button).toHaveClass('is-disabled');
                    deferred.resolve();
                    expect(button).not.toHaveClass('is-disabled');
                });
            });
        });
    }
);
