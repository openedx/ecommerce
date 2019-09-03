transaction_detail_response_error_data = {
    "result_code": "Error",
    "message_code": "E00050",
    "message_text": "fake_error_description",
}

transaction_detail_response_success_data = {
    "result_code": "Ok",
    "message_code": "I00001",
    "message_text": "Successful",
}

refund_success_response = """
    <messages>
        <message>
            <code>1</code>
            <description>fake code description</description>
        </message>
    </messages> """

refund_error_response = """
    <errors>
        <error>
            <errorCode>54</errorCode>
            <errorText>fake error text</errorText>
        </error>
    </errors> """

refund_response_template = """
    <createTransactionRequest xmlns="AnetApi/xml/v1/schema/AnetApiSchema.xsd">
        <messages>
            <resultCode>{result_code}</resultCode>
            <message>
                <code>{message_code}</code>
                <text>fake_message_text</text>
            </message>
        </messages>
        <transactionResponse>
            <responseCode>{response_code}</responseCode>
            <authCode/>
            <avsResultCode>P</avsResultCode>
            <cvvResultCode/>
            <cavvResultCode/>
            <transId>{transaction_id}</transId>
            <refTransID>{reference_transaction_id}</refTransID>
            <transHash/>
            <testRequest>0</testRequest>
            <accountNumber>XXXX1111</accountNumber>
            <accountType>Visa</accountType>
            {sub_template}
            <transHashSha2>fake_code</transHashSha2>
        </transactionResponse>
    </createTransactionRequest> """

hosted_payment_token_response_template = """
    <getHostedPaymentPageRequest xmlns="AnetApi/xml/v1/schema/AnetApiSchema.xsd">
        <messages>
            <resultCode>Ok</resultCode>
            <message>
                <code>I00001</code>
                <text>Successful.</text>
            </message>
        </messages>
        <token>test_token</token>
    </getHostedPaymentPageRequest> """


transaction_detail_response_template = """
    <getTransactionDetailsRequest xmlns="AnetApi/xml/v1/schema/AnetApiSchema.xsd">
        <messages>
            <resultCode>{result_code}</resultCode>
            <message>
                <code>{message_code}</code>
                <text>{message_text}.</text>
            </message>
        </messages>
        <transaction>
            <transId>{transaction_id}</transId>
            <submitTimeUTC>2019-08-28T09:02:24.39Z</submitTimeUTC>
            <submitTimeLocal>2019-08-28T02:02:24.39</submitTimeLocal>
            <transactionType>{transaction_type}</transactionType>
            <transactionStatus>{transaction_status}</transactionStatus>
            <responseCode>{transaction_response_code}</responseCode>
            <responseReasonCode>{transaction_response_reason_code}</responseReasonCode>
            <responseReasonDescription>{transaction_response_reason_description}</responseReasonDescription>
            <authCode>7YWTCT</authCode>
            <AVSResponse>Y</AVSResponse>
            <cardCodeResponse>P</cardCodeResponse>
            <order>
                <invoiceNumber>{order_invoice_number}</invoiceNumber>
                <discountAmount>0.0</discountAmount>
                <taxIsAfterDiscount>false</taxIsAfterDiscount>
            </order>
            <authAmount>{auth_amount}</authAmount>
            <settleAmount>{settle_amount}</settleAmount>
            <lineItems>
                <lineItem>
                    <itemId>{line_item_id}</itemId>
                    <name>{line_item_name}</name>
                    <description>{line_item_description}</description>
                    <quantity>{line_item_quantity}</quantity>
                    <unitPrice>{line_item_unit_price}</unitPrice>
                    <taxable>false</taxable>
                    <taxRate>0.0</taxRate>
                    <taxAmount>0.0</taxAmount>
                    <nationalTax>0.0</nationalTax>
                    <localTax>0.0</localTax>
                    <vatRate>0.0</vatRate>
                    <alternateTaxRate>0.0</alternateTaxRate>
                    <alternateTaxAmount>0.0</alternateTaxAmount>
                    <totalAmount>0.0</totalAmount>
                    <discountRate>0.0</discountRate>
                    <discountAmount>0.0</discountAmount>
                    <taxIncludedInTotal>false</taxIncludedInTotal>
                    <taxIsAfterDiscount>false</taxIsAfterDiscount>
                </lineItem>
            </lineItems>
            <taxExempt>false</taxExempt>
            <payment>
                <creditCard>
                    <cardNumber>{card_number}</cardNumber>
                    <expirationDate>XXXX</expirationDate>
                    <cardType>{card_type}</cardType>
                </creditCard>
            </payment>
            <billTo>
                <firstName>{first_name}</firstName>
                <lastName>{last_name}</lastName>
                <country>{country}</country>
            </billTo>
            <recurringBilling>false</recurringBilling>
            <customerIP>10.141.8.51</customerIP>
            <product>Card Not Present</product>
            <marketType>eCommerce</marketType>
        </transaction>
        <clientId>accept-hosted</clientId>
    </getTransactionDetailsRequest> """
