from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional

from django_prices_vatlayer.utils import get_tax_for_rate, get_tax_rates_for_country
from prices import Money, MoneyRange, TaxedMoney, TaxedMoneyRange

from ...checkout import base_calculations
from ...core.prices import quantize_price
from ...core.taxes import charge_taxes_on_shipping, include_taxes_in_prices
from ...discount import VoucherType
from ...order.utils import get_total_order_discount_excluding_shipping

if TYPE_CHECKING:
    from ...checkout.fetch import CheckoutInfo, CheckoutLineInfo
    from ...discount import DiscountInfo
    from ...order.models import Order, OrderLine

DEFAULT_TAX_RATE_NAME = "standard"


@dataclass
class VatlayerConfiguration:
    access_key: str
    excluded_countries: Optional[List[str]]
    countries_from_origin: Optional[List[str]]
    origin_country: Optional[str]


def _convert_to_naive_taxed_money(base, taxes, rate_name):
    """Naively convert Money to TaxedMoney.

    It is meant for consistency with price handling logic across the codebase,
    passthrough other money types.
    """
    if isinstance(base, Money):
        return TaxedMoney(net=base, gross=base)
    if isinstance(base, MoneyRange):
        return TaxedMoneyRange(
            apply_tax_to_price(taxes, rate_name, base.start),
            apply_tax_to_price(taxes, rate_name, base.stop),
        )
    if isinstance(base, (TaxedMoney, TaxedMoneyRange)):
        return base
    raise TypeError("Unknown base for flat_tax: %r" % (base,))


def apply_tax_to_price(taxes, rate_name, base):
    if not taxes or not rate_name:
        return _convert_to_naive_taxed_money(base, taxes, rate_name)

    if rate_name in taxes:
        tax_to_apply = taxes[rate_name]["tax"]
    else:
        tax_to_apply = taxes[DEFAULT_TAX_RATE_NAME]["tax"]

    keep_gross = include_taxes_in_prices()
    return tax_to_apply(base, keep_gross=keep_gross)


def get_taxes_for_country(country):
    tax_rates = get_tax_rates_for_country(country.code)
    if tax_rates is None:
        return None

    taxes = {
        DEFAULT_TAX_RATE_NAME: {
            "value": tax_rates["standard_rate"],
            "tax": get_tax_for_rate(tax_rates),
        }
    }
    if tax_rates["reduced_rates"]:
        taxes.update(
            {
                rate_name: {
                    "value": tax_rates["reduced_rates"][rate_name],
                    "tax": get_tax_for_rate(tax_rates, rate_name),
                }
                for rate_name in tax_rates["reduced_rates"]
            }
        )
    return taxes


def get_tax_rate_by_name(rate_name, taxes=None):
    """Return value of tax rate for current taxes."""
    if not taxes or not rate_name:
        tax_rate = 0
    elif rate_name in taxes:
        tax_rate = taxes[rate_name]["value"]
    else:
        tax_rate = taxes[DEFAULT_TAX_RATE_NAME]["value"]

    return tax_rate


def get_taxed_shipping_price(shipping_price, taxes):
    """Calculate shipping price based on settings and taxes."""
    if not charge_taxes_on_shipping():
        taxes = None
    return apply_tax_to_price(taxes, DEFAULT_TAX_RATE_NAME, shipping_price)


def apply_checkout_discount_on_checkout_line(
    checkout_info: "CheckoutInfo",
    lines: List["CheckoutLineInfo"],
    checkout_line_info: "CheckoutLineInfo",
    discounts: Iterable["DiscountInfo"],
    line_price: Money,
):
    """Calculate the checkout line price with discounts.

    Include the entire order voucher discount.
    """
    voucher = checkout_info.voucher
    if not voucher or voucher.type == VoucherType.SHIPPING:
        return line_price

    line_quantity = checkout_line_info.line.quantity
    total_discount_amount = checkout_info.checkout.discount_amount
    line_total_price = line_price * line_quantity
    currency = checkout_info.checkout.currency

    # if the checkout has only one line, the hole discount amount will be applied
    # to this line
    if len(lines) == 1:
        return (
            line_total_price - Money(total_discount_amount, currency)
        ) / line_quantity

    # if the checkout has more lines we need to propagate the discount amount
    # proportionally to total prices of items
    lines_total_prices = [
        base_calculations.calculate_base_line_unit_price(
            line_info,
            checkout_info.channel,
            discounts,
        ).price_with_discounts.amount
        * line_info.line.quantity
        for line_info in lines
        if line_info.line.id != checkout_line_info.line.id
    ]

    total_price = sum(lines_total_prices) + line_total_price.amount

    last_element = lines[-1].line.id == checkout_line_info.line.id
    if last_element:
        discount_amount = _calculate_discount_for_last_element_in_qs(
            lines_total_prices, total_price, total_discount_amount, currency
        )
    else:
        discount_amount = quantize_price(
            line_total_price.amount / total_price * total_discount_amount, currency
        )
    return quantize_price(
        (line_total_price - Money(discount_amount, currency)) / line_quantity, currency
    )


def apply_order_discount_to_order_unit_price(
    order: "Order",
    order_line: "OrderLine",
):
    """Calculate the order line price with discounts.

    Include the entire order voucher discount.
    """
    if (
        not order.voucher_id
        or order.voucher.type == VoucherType.SHIPPING  # type: ignore
    ):
        return order_line.base_unit_price

    currency = order.currency
    total_discount_amount = get_total_order_discount_excluding_shipping(order).amount
    line_total_price = order_line.base_unit_price * order_line.quantity

    # if the order has only one line, the hole discount amount will be applied
    # to this line
    if order.lines.count() == 1:
        return (
            line_total_price - Money(total_discount_amount, currency)
        ) / order_line.quantity

    order_lines = order.lines.all()

    # if the order has more lines we need to propagate the discount amount
    # proportionally to total prices of items
    lines_total_prices = [
        line.base_unit_price.amount * line.quantity
        for line in order_lines
        if line.id != order_line.id
    ]
    total_price = sum(lines_total_prices) + line_total_price.amount

    last_element = order_lines.last().pk == order_line.pk  # type: ignore
    if last_element:
        discount_amount = _calculate_discount_for_last_element_in_qs(
            lines_total_prices, total_price, total_discount_amount, currency
        )
    else:
        discount_amount = quantize_price(
            line_total_price.amount / total_price * total_discount_amount, currency
        )
    return quantize_price(
        (line_total_price - Money(discount_amount, currency)) / order_line.quantity,
        currency,
    )


def _calculate_discount_for_last_element_in_qs(
    lines_total_prices, total_price, total_discount_amount, currency
):
    """Calculate the discount for last element of query set.

    If the given line is last on the list we should calculate the discount by difference
    between total discount amount and sum of discounts applied to rest of the lines,
    otherwise the sum of discounts won't be equal to the discount amount.
    """
    sum_of_discounts_other_elements = sum(
        [
            quantize_price(
                line_total_price / total_price * total_discount_amount,
                currency,
            )
            for line_total_price in lines_total_prices
        ]
    )
    return total_discount_amount - sum_of_discounts_other_elements
