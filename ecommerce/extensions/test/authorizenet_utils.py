import json
from lxml import objectify, etree
from ecommerce.extensions.test.constants import (
    hosted_payment_token_response_template,
    transaction_detail_response_template,
    refund_response_template,
    refund_error_response,
    refund_success_response,
    transaction_detail_response_success_data
)
from oscar.test.factories import CountryFactory


def get_authorizenet_transaction_reponse_xml(transaction_id, basket, data):
    line_item = basket.all_lines()[0]
    line_item_unit_price = line_item.line_price_incl_tax_incl_discounts / line_item.quantity
    transaction_detail_xml = transaction_detail_response_template.format(
        result_code = data.get("result_code"),
        message_code = data.get("message_code"),
        message_text = data.get(" message_text"),
        transaction_id = transaction_id,
        transaction_type = "authCaptureTransaction",
        transaction_status = "capturedPendingSettlement",
        transaction_response_code = 1,
        transaction_response_reason_code = 1,
        transaction_response_reason_description = "Approval",
        order_invoice_number = basket.order_number,
        auth_amount = unicode(basket.total_incl_tax),
        settle_amount = unicode(basket.total_incl_tax),
        line_item_id = line_item.product.course_id,
        line_item_name = line_item.product.course_id,
        line_item_description = line_item.product.title,
        line_item_quantity = line_item.quantity,
        line_item_unit_price = line_item_unit_price,
        card_number = "XXXX1111",
        card_type = "Visa",
        first_name = "fake_first_name",
        last_name = "fake_last_name",
        country = CountryFactory().iso_3166_1_a2
    )
    return transaction_detail_xml

def get_authorizenet_refund_reponse_xml(data):
    refund_xml = refund_response_template.format(
        result_code = data.get("result_code"),
        message_code = data.get("message_code"),
        response_code = data.get("response_code"),
        transaction_id = data.get("transaction_id"),
        reference_transaction_id = data.get("reference_transaction_id"),
        sub_template = data.get("sub_template")
    )
    return refund_xml

def record_transaction_detail_processor_response(processor, reference_trans_id, basket):
    response_data = transaction_detail_response_success_data
    transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
        reference_trans_id, basket, response_data)
    transaction_response = objectify.fromstring(transaction_detail_xml)

    transaction_dict = json.dumps(
        transaction_response,
        default=lambda o: o.__dict__ if getattr(o, '__dict__') else str(o)
    )
    processor.record_processor_response(
        transaction_dict, transaction_id=reference_trans_id, basket=basket)
