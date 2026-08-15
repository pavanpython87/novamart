from src.cleaning.status_harmonizer import harmonize_order_status, harmonize_shipment_status


def test_harmonize_order_status_shopify_financial():
    assert harmonize_order_status("paid") == "paid"
    assert harmonize_order_status("voided") == "cancelled"


def test_harmonize_order_status_shopify_fulfillment():
    assert harmonize_order_status("fulfilled") == "shipped"
    assert harmonize_order_status("partial") == "partially_shipped"


def test_harmonize_order_status_amazon():
    assert harmonize_order_status("Shipped") == "shipped"
    assert harmonize_order_status("Cancelled") == "cancelled"


def test_harmonize_order_status_unknown_returns_none():
    assert harmonize_order_status("something_weird") is None


def test_harmonize_order_status_none_returns_none():
    assert harmonize_order_status(None) is None


def test_harmonize_shipment_status_fedex_usps_text():
    assert harmonize_shipment_status("DELIVERED") == "delivered"
    assert harmonize_shipment_status("PRE_TRANSIT") == "pending"


def test_harmonize_shipment_status_ups_letter_codes():
    assert harmonize_shipment_status("D") == "delivered"
    assert harmonize_shipment_status("X") == "exception"
