import pandas as pd

from src.transform.revenue_calculator import (
    amazon_fba_fee,
    calculate_gross_profit,
    calculate_net_revenue,
    calculate_order_economics,
    calculate_order_economics_batch,
    calculate_payment_processing_fee,
    calculate_platform_fee,
)


def test_amazon_fba_fee_tiers():
    assert amazon_fba_fee(0.5) == 3.22
    assert amazon_fba_fee(2.0) == 4.75
    assert amazon_fba_fee(25.0) == 19.99


def test_calculate_platform_fee_amazon_uses_category_referral_and_fba():
    fee = calculate_platform_fee("amazon", 100.0, category="Audio", weight_lbs=0.5)
    assert fee == 8.0 + 3.22


def test_calculate_platform_fee_amazon_unknown_category_uses_default():
    fee = calculate_platform_fee("amazon", 100.0, category="Unknown", weight_lbs=0.5)
    assert fee == 15.0 + 3.22


def test_calculate_platform_fee_shopify():
    fee = calculate_platform_fee("shopify", 100.0)
    assert fee == round(100.0 * 0.029 + 0.30, 2)


def test_calculate_platform_fee_pos_is_zero():
    assert calculate_platform_fee("pos", 100.0) == 0.0


def test_calculate_payment_processing_fee_card():
    fee = calculate_payment_processing_fee("card", 100.0)
    assert fee == round(100.0 * 0.029 + 0.30, 2)


def test_calculate_payment_processing_fee_cash_is_zero():
    assert calculate_payment_processing_fee("cash", 100.0) == 0.0


def test_calculate_payment_processing_fee_paypal():
    fee = calculate_payment_processing_fee("paypal", 100.0)
    assert fee == round(100.0 * 0.035 + 0.49, 2)


def test_calculate_net_revenue_full_decomposition():
    order = {
        "channel": "shopify",
        "gross_revenue": 100.0,
        "payment_method": "card",
        "discount_amount": 5.0,
        "refund_amount": 0.0,
        "restocking_fee": 0.0,
    }
    result = calculate_net_revenue(order)
    platform_fee = round(100.0 * 0.029 + 0.30, 2)
    payment_fee = round(100.0 * 0.029 + 0.30, 2)
    expected_net = round(100.0 - platform_fee - payment_fee - 0.0 - 5.0, 2)
    assert result["net_revenue"] == expected_net
    assert result["discounts_and_promotions"] == 5.0


def test_calculate_net_revenue_with_refund_and_restocking_fee():
    order = {
        "channel": "pos",
        "gross_revenue": 50.0,
        "payment_method": "cash",
        "discount_amount": 0.0,
        "refund_amount": 20.0,
        "restocking_fee": 2.0,
    }
    result = calculate_net_revenue(order)
    assert result["returns_and_refunds"] == 18.0
    assert result["net_revenue"] == 32.0


def test_calculate_gross_profit():
    order = {"unit_cost": 10.0, "quantity": 2, "net_revenue": 50.0}
    result = calculate_gross_profit(order)
    assert result["cogs"] == 20.0
    assert result["gross_profit"] == 30.0


def test_calculate_order_economics_end_to_end():
    order = {
        "channel": "pos",
        "gross_revenue": 100.0,
        "payment_method": "cash",
        "discount_amount": 0.0,
        "refund_amount": 0.0,
        "restocking_fee": 0.0,
        "unit_cost": 40.0,
        "quantity": 1,
    }
    result = calculate_order_economics(order)
    assert result["net_revenue"] == 100.0
    assert result["cogs"] == 40.0
    assert result["gross_profit"] == 60.0


def test_calculate_order_economics_batch():
    df = pd.DataFrame([
        {"channel": "pos", "gross_revenue": 100.0, "payment_method": "cash",
         "discount_amount": 0.0, "refund_amount": 0.0, "restocking_fee": 0.0,
         "unit_cost": 40.0, "quantity": 1},
        {"channel": "shopify", "gross_revenue": 50.0, "payment_method": "card",
         "discount_amount": 0.0, "refund_amount": 0.0, "restocking_fee": 0.0,
         "unit_cost": 10.0, "quantity": 1},
    ])
    result = calculate_order_economics_batch(df)
    assert len(result) == 2
    assert "gross_profit" in result.columns


def test_calculate_order_economics_batch_empty():
    df = pd.DataFrame(columns=["channel", "gross_revenue"])
    result = calculate_order_economics_batch(df)
    assert result.empty
    assert "net_revenue" in result.columns
