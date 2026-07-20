# ogun/ogun/utils/service_data_controller.py

import frappe
from frappe.model.document import Document
from frappe.utils import flt  # já resolveu esse import antes, lembra do NameError


class ServiceDataController(Document):
    """
    Classe base compartilhada entre Orçamento e Ordem de Serviço.
    Centraliza cálculo de totais e validações comuns aos dois documentos.
    Documentos filhos devem chamar super().validate() explicitamente.
    """

    def validate(self):
        self.calculate_totals()
        self.validate_itens_nao_vazio()

    def calculate_totals(self):
        """
        Recalcula amount de cada item e o total do documento.
        Mesma lógica que você já tinha implementado em Ordem de Serviço,
        agora compartilhada.
        """
        total = 0
        for item in self.itens:
            item.amount = flt(item.qty) * flt(item.rate)
            total += item.amount

        self.total = total

    def validate_itens_nao_vazio(self):
        """
        Regra comum: nenhum documento de serviço pode ser salvo sem
        pelo menos 1 item.
        """
        if not self.itens:
            frappe.throw("Adicione ao menos um item antes de salvar.")