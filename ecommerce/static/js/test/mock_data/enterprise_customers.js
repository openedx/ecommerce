define([], function() {
    'use strict';

    var customers = [
        {
            id: '29c466f1583b47279265d0a1fd7012a3',
            name: 'Battlestar Galactica'
        },
        {
            id: 'e7d4a3c6f510405d968e28e098ddb543',
            name: 'Starship Enterprise'
        },
        {
            id: '42a30ade47834489a607cd0f52ba13cf',
            name: 'Millenium Falcon'
        }
    ];
    customers.fetch = function(params) {
        var input;
        if (params) {
            input = params.data.startswith;
            return customers.filter(function(customer) { return customer.name.includes(input); });
        }
        return customers;
    };
    customers.findWhere = function(params) {
        var foundCustomer = customers.find(function(customer) {
            return customer.name === params.name;
        });
        if (foundCustomer) {
            foundCustomer.toJSON = function() {
                return foundCustomer;
            };
        }
        return foundCustomer;
    };
    return customers;
});
