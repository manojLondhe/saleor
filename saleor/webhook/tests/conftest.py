from decimal import Decimal
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def checkout_with_prices(
    checkout_with_items,
    address,
    address_other_country,
    warehouse,
    customer_user,
    shipping_method,
):
    lines = checkout_with_items.lines.all()
    for i, line in enumerate(lines, start=1):
        line.unit_price_net_amount = Decimal("10.00") + Decimal(i)
        line.unit_price_gross_amount = Decimal("10.00") + Decimal(i) * Decimal("1.1")
        line.unit_price_with_discounts_net_amount = (
            Decimal("10.00") + Decimal(i) - Decimal("0.30")
        )
        line.unit_price_with_discounts_gross_amount = (
            Decimal("10.00") + Decimal(i) * Decimal("1.1") - Decimal("0.30")
        )

    checkout_with_items.discount_amount = Decimal("0.00")
    checkout_with_items.user = customer_user
    checkout_with_items.billing_address = address
    checkout_with_items.shipping_address = address_other_country
    checkout_with_items.shipping_method = shipping_method
    checkout_with_items.collection_point = warehouse
    checkout_with_items.subtotal_net_amount = Decimal("100.00")
    checkout_with_items.subtotal_gross_amount = Decimal("123.00")
    checkout_with_items.total_net_amount = Decimal("150.00")
    checkout_with_items.total_gross_amount = Decimal("178.00")

    checkout_with_items.lines.bulk_update(
        lines,
        [
            "unit_price_net_amount",
            "unit_price_gross_amount",
            "unit_price_with_discounts_net_amount",
            "unit_price_with_discounts_gross_amount",
        ],
    )

    checkout_with_items.save(
        update_fields=[
            "discount_amount",
            "user",
            "billing_address",
            "shipping_address",
            "shipping_method",
            "collection_point",
            "subtotal_net_amount",
            "subtotal_gross_amount",
            "total_net_amount",
            "total_gross_amount",
        ]
    )

    return checkout_with_items


@pytest.fixture
def mocked_fetch_checkout():
    def mocked_fetch_side_effect(
        checkout_info, manager, lines, address, discounts, force_update=False
    ):
        return checkout_info, lines

    with patch(
        "saleor.checkout.calculations.fetch_checkout_prices_if_expired",
        new=Mock(side_effect=mocked_fetch_side_effect),
    ) as mocked_fetch:
        yield mocked_fetch


@pytest.fixture
def mocked_fetch_order():
    def mocked_fetch_side_effect(order, manager, lines, force_update=False):
        return order, lines

    with patch(
        "saleor.order.calculations.fetch_order_prices_if_expired",
        new=Mock(side_effect=mocked_fetch_side_effect),
    ) as mocked_fetch:
        yield mocked_fetch
