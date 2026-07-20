// ogun/ogun/doctype/orcamento/orcamento.js

frappe.ui.form.on('Orçamento', {
    refresh(frm) {
        // Só mostra o botão se o orçamento já estiver salvo (tem um "name")
        // e status permitir conversão
        if (!frm.is_new() && frm.doc.status === 'Aprovado') {
            frm.add_custom_button('Criar Ordem de Serviço', () => {
                frappe.model.open_mapped_doc({
                    method: 'ogun.ogun.doctype.orcamento.orcamento.make_ordem_de_servico',
                    frm: frm,
                });
            });
        }
    },
});