# ogun/ogun/utils/permissions.py

import frappe


def ensure_user_has_role(user: str, role: str, field_label: str = "usuário") -> None:
    """
    Garante que o usuário informado possui a Role indicada.
    Lança frappe.throw (interrompe o save) caso contrário.

    Uso típico: validar campos Link -> User que representam um papel
    específico no fluxo (ex: técnico responsável, aprovador, etc.).
    """
    if role not in frappe.get_roles(user):
        frappe.throw(
            f"O {field_label} '{user}' não possui a Role '{role}'."
        )