// Copyright (c) 2026, NeoGen and contributors
// For license information, please see license.txt

// ogun/ogun/doctype/ordem_de_servico/ordem_de_servico.js

frappe.ui.form.on('Ordem de Serviço', {
    onload(frm) {
        frm.set_query('tecnico_responsavel', () => {
            return {
                query: 'frappe.core.doctype.user.user.user_query',
                filters: {
                    role: 'Tecnico',
                },
            };
        });
    },
});
