# ogun/ogun/doctype/ordem_de_servico/ordem_de_servico.py

import frappe
from ogun.ogun.utils.service_data_controller import ServiceDataController
from ogun.ogun.utils.permissions import ensure_user_has_role


class OrdemDeServico(ServiceDataController):
    def validate(self):
        super().validate()
        self.validate_tecnico_responsavel()

    def validate_tecnico_responsavel(self):
        if self.status == "Em Andamento" and not self.tecnico_responsavel:
            frappe.throw(
                "Defina um técnico responsável antes de iniciar a Ordem de Serviço."
            )

        if self.tecnico_responsavel:
            ensure_user_has_role(
                self.tecnico_responsavel,
                "Tecnico",
                field_label="técnico responsável",
            )