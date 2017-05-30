define([
    'underscore',
    'utils/credit_card'
],
    function(_,
             CreditCardUtils) {
        'use strict';

        describe('CreditCardUtils', function() {
            var validCardList = [
                {number: '378282246310005', name: 'amex', type: '003'},
                {number: '30569309025904', name: 'diners', type: '005'},
                {number: '6011111111111117', name: 'discover', type: '004'},
                {number: '3530111333300000', name: 'jcb', type: '007'},
                {number: '5105105105105100', name: 'mastercard', type: '002'},
                {number: '4111111111111111', name: 'visa', type: '001'},
                {number: '6759649826438453', name: 'maestro', type: '042'}
            ];

            describe('isValidCreditCard', function() {
                it('should return true for the valid credit cards', function() {
                    _.each(validCardList, function(cardNum) {
                        expect(CreditCardUtils.isValidCardNumber(cardNum.number)).toEqual(true);
                    });
                });

                it('should return false for the invalid credit cards', function() {
                    var invalidCards = ['3782831abc0005', '305699909025904', '00000'];
                    _.each(invalidCards, function(cardNum) {
                        expect(CreditCardUtils.isValidCardNumber(cardNum)).toEqual(false);
                    });
                });
            });

            describe('getCreditCardType', function() {
                it('should recognize the right card', function() {
                    _.each(validCardList, function(card) {
                        var cardType = CreditCardUtils.getCreditCardType(card.number);
                        expect(cardType.name).toEqual(card.name);
                        expect(cardType.type).toEqual(card.type);
                    });
                });

                it('should not return anything for unrecognized credit cards', function() {
                    var invalidNum = '123123123';
                    var invalidCard = CreditCardUtils.getCreditCardType(invalidNum);
                    expect(typeof invalidCard).toEqual('undefined');
                });
            });
        });
    }
);
