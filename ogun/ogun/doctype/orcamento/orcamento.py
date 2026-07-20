# Copyright (c) 2026, NeoGen and contributors
# For license information, please see license.txt

# import frappe
import frappe
from ogun.ogun.utils.service_data_controller import ServiceDataController
from frappe.model.mapper import get_mapped_doc

class Orcamento(ServiceDataController):
    def validate(self):
        super().validate()  # roda calculate_totals + validate_itens_nao_vazio
        self.validate_validade()

    def validate_validade(self):
        """
        Regra específica de Orçamento: alerta se a data de validade
        já passou (regra que não faz sentido em Ordem de Serviço).
        """
        from frappe.utils import getdate, today

        if self.data_validade and getdate(self.data_validade) < getdate(today()):
            frappe.msgprint("Atenção: este orçamento já está vencido.", alert=True)
    
@frappe.whitelist()
def make_ordem_de_servico(source_name, target_doc=None):
    """
    Cria uma Ordem de Serviço a partir de um Orçamento existente.
    Equivalente a um mapper Orcamento -> OrdemDeServicoDto no Nest,
    mas resolvido declarativamente pelo Frappe.
    """

    def set_missing_values(source, target):
        # Campos que não vêm de uma cópia direta, e sim de uma regra
        target.orcamento_ref = source.name
        target.status = "Pendente"

    doc = get_mapped_doc(
        "Orcamento",
        source_name,
        {
            "Orcamento": {
                "doctype": "Ordem De Servico",
                # field_map: {campo_origem: campo_destino}
                # como usamos os mesmos fieldnames (Seção 3, Passo 1),
                # não precisamos mapear nada aqui
            },
            "Item Fluxo": {
                "doctype": "Item Fluxo",
                # Child table idêntica -> copiada 1:1 automaticamente
            },
        },
        target_doc,
        set_missing_values,
    )

    return doc