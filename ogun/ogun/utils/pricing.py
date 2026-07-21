import frappe
from frappe.utils import flt


class ItemPriceResolver:
    """
    Resolve o preço de um item numa Price List específica.

    Ponto único de expansão: quando você precisar de lógica mais
    sofisticada (preço por grupo de cliente, promoções, regras por
    company, etc), é aqui que entra uma nova estratégia — sem tocar
    nos controllers dos doctypes que consomem isso.
    """

    def __init__(self, price_list):
        self.price_list = price_list

    def get_rate(self, item_code):
        if not item_code:
            return 0

        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": self.price_list},
            "price_list_rate",
        )
        return flt(rate)