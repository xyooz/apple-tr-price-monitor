import unittest
from src.monitor import parse_products

def page(count=6, currency="US$"):
    return "<html><body>" + " ".join(
        f"<div>iTunes Gift Card {10 * (i + 1)} TL TR {currency} {2 * (i + 1):.2f} {currency} {1.8 * (i + 1):.2f}</div>"
        for i in range(count)
    ) + "</body></html"

class ProductParserTests(unittest.TestCase):
    def test_discounted_price(self):
        products = parse_products(page())
        self.assertEqual(len(products), 6)
        self.assertEqual(products[0]["price_usd"], 1.8)
        self.assertEqual(products[-1]["price_usd"], 10.8)

    def test_other_currency_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "0 个面额"):
            parse_products(page(currency="₩"))

    def test_insufficient_products_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "2 个面额"):
            parse_products(page(count=2))
