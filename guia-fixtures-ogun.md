# Fixtures no Frappe: Tornando o Ogun Auto-configurável
### Como garantir que qualquer site com ERPNext + Ogun instalado tenha a estrutura certa automaticamente

> **Contexto:** No guia anterior, você criou os Custom Fields e o Client Script via UI (Customize Form). Isso funciona, mas tem um problema grave: essas configurações vivem **só no banco de dados do seu site local**. Se você instalar o Ogun em outro servidor, ou se um colaborador clonar o repo e criar um novo site, nada disso vai estar lá. Fixtures resolvem exatamente isso.

---

## O Problema: Configuração que Não Viaja com o Código

Imagine que você terminou o desenvolvimento local e vai fazer deploy do Ogun em produção. Você faz:

```bash
# No servidor de produção
bench get-app ogun https://github.com/seu-usuario/ogun
bench --site producao.erp.localhost install-app ogun
bench --site producao.erp.localhost migrate
```

O app está instalado. Os DocTypes `Celular` e `Notebook` existem. O `hooks.py` está configurado. Mas quando você abre um Customer... a seção "Dispositivos Registrados" não aparece. O Client Script não existe. Os Custom Fields sumiram.

**Por quê?** Porque você os criou pela UI — eles vivem no banco de dados do site de desenvolvimento, não nos arquivos do app.

```
Desenvolvimento Local          Produção
┌─────────────────────┐        ┌─────────────────────┐
│  Git Repository     │  ──→   │  Git Repository     │
│  ✅ ogun/hooks.py   │        │  ✅ ogun/hooks.py   │
│  ✅ ogun/doctype/   │        │  ✅ ogun/doctype/   │
│  ✅ ogun/utils/     │        │  ✅ ogun/utils/     │
└─────────────────────┘        └─────────────────────┘
         +                              +
┌─────────────────────┐        ┌─────────────────────┐
│  Banco de Dados     │        │  Banco de Dados     │
│  ✅ Custom Fields   │   ≠    │  ❌ Custom Fields   │
│  ✅ Client Script   │        │  ❌ Client Script   │
└─────────────────────┘        └─────────────────────┘
```

Fixtures fecham essa lacuna: eles são **arquivos JSON no seu repositório** que o Frappe importa automaticamente para o banco de dados ao rodar `bench migrate`.

---

## O Que São Fixtures?

Fixtures são arquivos JSON que representam **registros do banco de dados** que devem sempre existir quando o seu app estiver instalado.

**Conceito de Engenharia Aplicado: Infrastructure as Code (IaC)**  
O mesmo princípio de ferramentas como Terraform, Ansible ou migrations do TypeORM/Prisma: o estado desejado da infraestrutura (aqui, do banco de dados) é descrito em código versionável, não configurado manualmente em cada ambiente. Qualquer servidor que rodar `migrate` converge para o mesmo estado.

**Como funciona o ciclo:**

```
Você escreve/exporta JSON  →  Commita no Git  →  bench migrate no servidor alvo
        ↓                                                    ↓
  ogun/fixtures/              qualquer site              Frappe lê os JSONs
  custom_field.json           com ogun                   e faz upsert no banco
  client_script.json          instalado
```

**O que é "upsert"?**  
Ao aplicar fixtures, o Frappe verifica: "esse registro já existe no banco?". Se sim, atualiza. Se não, cria. É idempotente — você pode rodar `migrate` dez vezes que o resultado é sempre o mesmo. Não cria duplicatas.

---

## Visão Geral do Que Vamos Fazer

1. **Declarar fixtures no `hooks.py`** — dizer ao Frappe quais tipos de dado são gerenciados pelo Ogun
2. **Escrever os JSONs de Custom Field** — a estrutura dos campos no Customer
3. **Escrever o JSON do Client Script** — o JavaScript que renderiza os dispositivos
4. **Verificar e testar** — exportar, limpar e reimportar para confirmar que funciona
5. **Entender o fluxo completo de instalação** — o que acontece quando alguém instala o Ogun do zero

---

## Parte 1 — Preparando a Estrutura de Diretórios

Fixtures ficam em um diretório chamado `fixtures/` dentro do seu app. Se ele não existir, crie:

```bash
mkdir -p apps/ogun/ogun/fixtures
```

A estrutura do seu app vai ficar assim:

```
ogun/
├── hooks.py
├── modules.txt
├── ogun/
│   ├── fixtures/                    ← novo diretório
│   │   ├── custom_field.json        ← campos no Customer
│   │   └── client_script.json       ← o script JS
│   ├── doctype/
│   │   ├── celular/
│   │   └── notebook/
│   └── utils/
│       └── customer_dashboard.py
└── ...
```

**Por que o diretório `fixtures/` fica dentro de `ogun/ogun/` e não na raiz?**  
A raiz do repositório (`ogun/`) é o pacote Python do app. O diretório `ogun/ogun/` é onde ficam os recursos do módulo principal. O Frappe procura fixtures no caminho `{app_name}/fixtures/` relativo ao módulo do app — por isso `ogun/ogun/fixtures/`.

---

## Parte 2 — Declarando Fixtures no `hooks.py`

Antes de criar os arquivos JSON, você precisa dizer ao Frappe quais DocTypes o Ogun gerencia como fixtures. Isso vai no `hooks.py`:

```python
# ogun/hooks.py

app_name = "ogun"
app_title = "Ogun"
# ... outros campos existentes ...

override_doctype_dashboards = {
    "Customer": "ogun.utils.customer_dashboard.get_data"
}

# ─── Fixtures ───────────────────────────────────────────────────────────────
# Cada entrada diz: "ao exportar/importar fixtures, inclua registros desse
# DocType que correspondam a esses filtros"
fixtures = [
    {
        "dt": "Custom Field",           # DocType a ser gerenciado
        "filters": [                    # Quais registros desse DocType
            ["dt", "=", "Customer"]     # Custom Fields do DocType Customer
        ]
    },
    {
        "dt": "Client Script",
        "filters": [
            ["dt", "=", "Customer"]     # Client Scripts do DocType Customer
        ]
    }
]
```

**O que cada parte significa:**

- `"dt"`: abreviação de "DocType" — o tipo de registro que estamos gerenciando como fixture
- `"filters"`: uma lista de condições no formato `[campo, operador, valor]`, igual ao sistema de filtros do Frappe em geral

**Por que usar filtros em vez de listar por nome?**  
Porque os registros (especialmente o Client Script) têm nomes auto-gerados como `a3f9b2c1`. Se você filtrasse por nome, teria que atualizar o `hooks.py` toda vez que recriar o script. Filtrando por `dt = Customer`, você captura automaticamente tudo que é do Customer — independente do nome gerado.

---

## Parte 3 — Escrevendo o JSON dos Custom Fields

### 3.1 A Estrutura de um Custom Field

Um registro de `Custom Field` no banco tem esta estrutura mínima:

```json
{
    "doctype": "Custom Field",
    "name": "Customer-dispositivos_section",
    "dt": "Customer",
    "fieldname": "dispositivos_section",
    "fieldtype": "Section Break",
    "label": "Dispositivos Registrados",
    "insert_after": "website_section"
}
```

Vamos entender cada campo:

| Campo | O que é | Analogia |
|---|---|---|
| `doctype` | Tipo do registro (sempre "Custom Field") | O "tipo" do objeto |
| `name` | Identificador único no banco | Primary key |
| `dt` | DocType alvo (onde o campo vai aparecer) | Nome da tabela que está sendo estendida |
| `fieldname` | Nome técnico do campo (snake_case) | Nome da coluna / chave no objeto |
| `fieldtype` | Tipo do campo (Section Break, HTML, Data...) | Tipo da coluna |
| `label` | Nome exibido na UI | Label do input |
| `insert_after` | Após qual campo este vai aparecer | Posição no formulário |

**Por que o `name` tem o formato `Customer-dispositivos_section`?**  
O Frappe usa esse padrão para Custom Fields: `{DocType}-{fieldname}`. É determinístico — dado um DocType e um fieldname, o nome sempre será o mesmo. Isso é fundamental para a idempotência: na segunda vez que o `migrate` rodar, o Frappe encontra esse `name` no banco e atualiza em vez de criar outro.

### 3.2 Descobrindo o valor correto de `insert_after`

O `insert_after` define onde no formulário o campo vai aparecer. Você precisa saber o `fieldname` do campo após o qual quer inserir.

**Como descobrir:** No Customize Form do Customer, passe o mouse sobre o campo que você quer que venha antes do seu. O `fieldname` aparece em cinza abaixo do label.

Para colocar a seção de dispositivos **no final do formulário**, use o último campo da última seção. Uma opção segura é usar o `fieldname` da seção "Website" que geralmente é a última:

```bash
# Você também pode consultar via bench console:
bench --site neogen.erp.localhost console

# No console Python:
frappe.get_meta("Customer").fields[-1].fieldname
# Retorna algo como: "dup_lead"
```

### 3.3 O arquivo `custom_field.json`

Crie o arquivo com os dois campos (Section Break e HTML):

```json
[
    {
        "doctype": "Custom Field",
        "name": "Customer-dispositivos_section",
        "dt": "Customer",
        "fieldname": "dispositivos_section",
        "fieldtype": "Section Break",
        "label": "Dispositivos Registrados",
        "insert_after": "dup_lead",
        "collapsible": 0,
        "module": "Ogun"
    },
    {
        "doctype": "Custom Field",
        "name": "Customer-dispositivos_html",
        "dt": "Customer",
        "fieldname": "dispositivos_html",
        "fieldtype": "HTML",
        "label": "Dispositivos",
        "insert_after": "dispositivos_section",
        "module": "Ogun"
    }
]
```

**Por que é um array?**  
Um arquivo de fixture representa todos os registros de um DocType que o seu app gerencia. O Frappe espera um array — mesmo que seja um único registro.

**O campo `module`:**  
Marca esses Custom Fields como pertencentes ao módulo "Ogun". Isso serve para filtragem e organização — não tem efeito funcional direto, mas é boa prática e ajuda na exportação futura.

**A ordem importa:**  
O primeiro item do array é criado primeiro. Como `dispositivos_html` depende de `dispositivos_section` existir (pelo `insert_after`), a seção precisa vir primeiro no array.

---

## Parte 4 — Escrevendo o JSON do Client Script

### 4.1 A Estrutura de um Client Script

```json
{
    "doctype": "Client Script",
    "name": "ogun-customer-dispositivos",
    "dt": "Customer",
    "view": "Form",
    "enabled": 1,
    "script": "..."
}
```

**Sobre o campo `name` do Client Script:**

Quando você cria um Client Script pela UI, o Frappe gera um `name` automático tipo `a3f9b2c1e5`. Para fixtures, você pode (e deve) definir um `name` descritivo manualmente — isso garante que o upsert funcione corretamente e fica mais legível.

Use um padrão que identifique claramente a origem: `{app}-{doctype}-{descrição}`.

### 4.2 O campo `script` com múltiplas linhas

JSON não suporta strings multilinha nativamente. Você tem duas opções:

**Opção A:** Escrever o script em uma linha só com `\n` (feio, difícil de manter)

**Opção B:** Usar um arquivo JS separado e referenciá-lo — mas o Frappe não suporta isso em fixtures

**Opção C (recomendada):** Usar a exportação automática do Frappe, que formata o JSON corretamente

Por enquanto, vamos escrever o JSON diretamente. O Frappe aceita o script como string com quebras de linha escapadas. Crie o arquivo assim:

```json
[
    {
        "doctype": "Client Script",
        "name": "ogun-customer-dispositivos",
        "dt": "Customer",
        "view": "Form",
        "enabled": 1,
        "script": "frappe.ui.form.on(\"Customer\", {\n    refresh(frm) {\n        if (!frm.doc.name) return;\n        renderDispositivos(frm);\n    }\n});\n\nasync function renderDispositivos(frm) {\n    const tiposDeDispositivo = [\"Celular\", \"Notebook\"];\n\n    const consultas = tiposDeDispositivo.map(tipo =>\n        frappe.db.get_list(tipo, {\n            filters: { cliente: frm.doc.name },\n            fields: [\"name\", \"marca\", \"modelo\", \"numero_serie\", \"status\"],\n            limit: 100\n        }).then(registros => registros.map(r => ({ ...r, _tipo: tipo })))\n    );\n\n    const resultados = await Promise.all(consultas);\n    const dispositivos = resultados.flat();\n    const $wrapper = frm.get_field(\"dispositivos_html\").$wrapper;\n\n    if (!dispositivos.length) {\n        $wrapper.html('<p class=\"text-muted\" style=\"padding: 10px 0;\">Nenhum dispositivo registrado para este cliente.</p>');\n        return;\n    }\n\n    const linhas = dispositivos.map(d => {\n        const url = `/app/${d._tipo.toLowerCase()}/${d.name}`;\n        const corStatus = d.status === \"Ativo\" ? \"green\" : \"gray\";\n        return `<tr><td>${d._tipo}</td><td><a href=\"${url}\">${d.name}</a></td><td>${d.marca || \"\u2014\"}</td><td>${d.modelo || \"\u2014\"}</td><td>${d.numero_serie || \"\u2014\"}</td><td><span class=\"indicator-pill ${corStatus}\">${d.status || \"\u2014\"}</span></td></tr>`;\n    }).join(\"\");\n\n    $wrapper.html(`<div style=\"margin-top:10px\"><table class=\"table table-bordered table-sm\"><thead class=\"grid-heading-row\"><tr><th>Tipo</th><th>ID</th><th>Marca</th><th>Modelo</th><th>N\u00ba de S\u00e9rie</th><th>Status</th></tr></thead><tbody>${linhas}</tbody></table></div>`);\n}"
    }
]
```

**Isso é doloroso de escrever à mão.** Por isso existe o caminho certo: criar pela UI primeiro, depois exportar. Veja a Parte 5.

---

## Parte 5 — O Caminho Certo: Exportar da UI

### 5.1 Por Que Exportar em Vez de Escrever?

Escrever JSON de fixture à mão é trabalhoso e propenso a erros (escapar strings, lembrar todos os campos obrigatórios, etc.). O fluxo profissional é:

```
Desenvolve pela UI (rápido, visual)
         ↓
Exporta como fixture (automático)
         ↓
Commita o JSON no Git (versionado)
         ↓
migrate em qualquer site (reproduzível)
```

### 5.2 Pré-requisito: o `hooks.py` deve estar configurado

Antes de exportar, certifique-se que o `hooks.py` já tem a declaração de `fixtures` da Parte 2. O comando de exportação usa essa configuração para saber o que exportar e para onde.

### 5.3 Criando pela UI (revisão rápida)

Se você já criou pela UI no guia anterior, os registros já estão no banco. Pule para o 5.4.

Se ainda não criou, faça agora:

**Custom Fields:** Customize Form → Customer → adicione `dispositivos_section` (Section Break) e `dispositivos_html` (HTML) → Update

**Client Script:** Busque "Client Script" → New → DocType: Customer, View: Form → cole o script → Save

### 5.4 Exportando

Com os registros criados no banco e o `hooks.py` configurado:

```bash
bench --site neogen.erp.localhost export-fixtures --app ogun
```

**O que esse comando faz:**

1. Lê a lista de `fixtures` declarada no `hooks.py` do Ogun
2. Para cada entrada, consulta o banco com os filtros declarados
3. Serializa os registros encontrados para JSON
4. Salva os arquivos em `apps/ogun/ogun/fixtures/`

Os arquivos gerados terão nomes baseados no DocType, em snake_case:

```
ogun/fixtures/
├── custom_field.json       ← os dois campos do Customer
└── client_script.json      ← o script JS
```

### 5.5 Inspecionando o que foi gerado

Abra os arquivos gerados e examine a estrutura. Você vai ver algo como:

**`custom_field.json`** (simplificado):
```json
[
    {
        "doctype": "Custom Field",
        "name": "Customer-dispositivos_section",
        "dt": "Customer",
        "fieldname": "dispositivos_section",
        "fieldtype": "Section Break",
        "label": "Dispositivos Registrados",
        "insert_after": "dup_lead",
        ...
    },
    {
        "doctype": "Custom Field",
        "name": "Customer-dispositivos_html",
        ...
    }
]
```

**`client_script.json`** (simplificado):
```json
[
    {
        "doctype": "Client Script",
        "name": "a3f9b2c1e5",
        "dt": "Customer",
        "view": "Form",
        "enabled": 1,
        "script": "frappe.ui.form.on(\"Customer\", {\n    refresh(frm) {\n..."
    }
]
```

**Atenção ao `name` do Client Script:**  
O Frappe gerou um hash como `a3f9b2c1e5`. Isso funciona, mas você pode (e deve) substituir por algo legível como `ogun-customer-dispositivos` — edite o JSON manualmente. Desde que o `name` seja único no sistema, qualquer string funciona.

### 5.6 Substituindo o nome do Client Script

Abra `client_script.json` e mude o campo `name`:

```json
[
    {
        "doctype": "Client Script",
        "name": "ogun-customer-dispositivos",   ← mude aqui
        ...
    }
]
```

**Cuidado:** se o script já existe no banco com o nome antigo (`a3f9b2c1e5`), o próximo `migrate` vai criar um novo registro com o nome novo, e o antigo vai permanecer. Para evitar duplicata, delete o script antigo pela UI antes de rodar o `migrate`.

---

## Parte 6 — Aplicando as Fixtures

### 6.1 Importando em um site que já tem os registros

Se você criou pela UI e depois exportou, os registros já estão no banco. Rodar `migrate` vai fazer **upsert** — atualizar os registros existentes com os dados do JSON. É seguro.

```bash
bench --site neogen.erp.localhost migrate
```

### 6.2 Testando a reprodutibilidade: simulando um novo site

Esse é o teste real. Você vai **deletar os registros do banco** e confirmar que o `migrate` os recria.

**Passo 1:** Delete os Custom Fields pela UI
- Customize Form → Customer → selecione `dispositivos_section` e `dispositivos_html` → Delete

**Passo 2:** Delete o Client Script pela UI
- Client Script → selecione o script do Customer → Delete

**Passo 3:** Verifique que sumiram
- Abra qualquer Customer — a seção "Dispositivos Registrados" não deve aparecer

**Passo 4:** Rode o migrate
```bash
bench --site neogen.erp.localhost migrate
```

Observe o output — você deve ver algo como:
```
Importing fixtures for ogun...
Importing Custom Field (2 records)
Importing Client Script (1 records)
```

**Passo 5:** Verifique que voltaram
- Abra qualquer Customer — a seção deve estar de volta, com o script funcionando

Se funcionou, as fixtures estão corretas. **Commita tudo:**

```bash
cd apps/ogun
git add ogun/fixtures/
git add hooks.py
git commit -m "feat: add fixtures for Customer device listing"
```

---

## Parte 7 — O Fluxo Completo de Instalação em um Novo Servidor

Agora veja o que acontece quando alguém (ou você mesmo em produção) instala o Ogun do zero:

```bash
# 1. Clonar o app (ou via bench get-app)
cd frappe-bench
bench get-app ogun https://github.com/seu-usuario/ogun

# 2. Instalar no site
bench --site producao.erp.localhost install-app ogun

# 3. Rodar migrate (isso aplica as fixtures automaticamente)
bench --site producao.erp.localhost migrate
```

O `install-app` + `migrate` garante que:

| O que é configurado | Como |
|---|---|
| DocTypes `Celular`, `Notebook` | Arquivos `doctype/*.json` do Ogun |
| Dashboard do Customer | `hooks.py` → `customer_dashboard.py` |
| Custom Fields no Customer | `fixtures/custom_field.json` |
| Client Script do Customer | `fixtures/client_script.json` |

**Nenhuma intervenção manual necessária.** O servidor de produção fica idêntico ao ambiente de desenvolvimento.

---

## Parte 8 — Manutenção: Como Atualizar as Fixtures

### Cenário: você mudou o script JS

1. Edite o Client Script pela UI no seu ambiente local (mais fácil que editar JSON)
2. Exporte novamente:
   ```bash
   bench --site neogen.erp.localhost export-fixtures --app ogun
   ```
3. O `client_script.json` é sobrescrito com a versão atualizada
4. Commit e push

### Cenário: você quer adicionar um novo campo ao Customer

1. Crie o campo pelo Customize Form
2. Exporte:
   ```bash
   bench --site neogen.erp.localhost export-fixtures --app ogun
   ```
3. O `custom_field.json` agora inclui o novo campo
4. Commit e push

### Cenário: você adicionou o DocType `PC` e quer incluir na listagem

Dois lugares para atualizar:

```python
# ogun/utils/customer_dashboard.py
"items": ["Celular", "Notebook", "PC"]   # adiciona PC
```

```javascript
// No Client Script (edite pela UI, depois exporte)
const tiposDeDispositivo = ["Celular", "Notebook", "PC"];
```

Depois de editar o script pela UI:
```bash
bench --site neogen.erp.localhost export-fixtures --app ogun
git add -A && git commit -m "feat: add PC to customer device listing"
```

---

## Recapitulando: O Estado Completo do Repositório

Ao final, seu app deve ter esta estrutura para o recurso de listagem de dispositivos:

```
ogun/
├── hooks.py                              ← override_doctype_dashboards + fixtures
├── ogun/
│   ├── fixtures/
│   │   ├── custom_field.json             ← Section Break + HTML no Customer
│   │   └── client_script.json           ← JS que renderiza a tabela
│   ├── doctype/
│   │   ├── celular/
│   │   │   └── celular.json             ← campo "cliente" Link → Customer
│   │   └── notebook/
│   │       └── notebook.json            ← campo "cliente" Link → Customer
│   └── utils/
│       └── customer_dashboard.py        ← define o grupo "Dispositivos" no dashboard
```

**O que cada arquivo contribui:**

```
hooks.py
  ├── override_doctype_dashboards → injeta customer_dashboard.py no Customer
  └── fixtures → declara o que exportar/importar

customer_dashboard.py → define os grupos do dashboard (contadores no topo)

custom_field.json → cria os campos "dispositivos_section" e "dispositivos_html"
                    no formulário do Customer

client_script.json → registra o JS que busca Celular + Notebook e renderiza a tabela
```

Cada arquivo tem uma responsabilidade única e bem definida. Juntos, eles transformam o Ogun de "um app que precisa de configuração manual" em "um app que se configura sozinho".
