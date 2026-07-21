import frappe
from frappe.model.document import Document
from frappe.utils import flt

from ogun.ogun.utils.pricing import ItemPriceResolver

DEFAULT_PRICE_LIST = "Venda Padrão"


class ServiceDataController(Document):
    """
    Classe base compartilhada entre Orçamento e Ordem de Serviço.
    Centraliza cálculo de totais, resolução de preço e validações
    comuns aos dois documentos. Documentos filhos devem chamar
    super().validate() explicitamente.
    """

    def validate(self):
        self.set_missing_rates()
        self.calculate_totals()
        self.validate_itens_nao_vazio()

    def set_missing_rates(self):
        """
        Se o rate de um item não veio preenchido na requisição,
        busca o valor na Price List configurada — mesma lógica que
        o Client Script já faz no client side, agora espelhada aqui
        pra cobrir criação via API/import, sem depender do form aberto.
        """
        resolver = ItemPriceResolver(self.get_price_list())

        for item in self.itens:
            # .get() em vez de .rate: o campo pode nem existir no dict
            # recebido, não só estar vazio/zerado
            if not item.get("rate"):
                item.rate = resolver.get_rate(item.get("item_code"))

    def get_price_list(self):
        """
        Ponto de extensão: doctypes filhos (ou o próprio documento,
        no futuro, via um campo `price_list` no formulário) podem
        sobrescrever isso pra escolher a lista dinamicamente — por
        tipo de cliente, por company, etc. Por enquanto, fixo.
        """
        return DEFAULT_PRICE_LIST

    def calculate_totals(self):
        """
        Recalcula amount de cada item e o total do documento.
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