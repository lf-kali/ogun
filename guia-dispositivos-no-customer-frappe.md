# Vinculando Dispositivos ao Cliente no ERPNext
### Um guia prático e conceitual para o projeto Neogen

> **Para quem é esse guia?**  
> Você tem experiência com NestJS, React e projetos fullstack em JS. Sabe scriptar em Python. Entende HTTP. Está aprendendo Frappe Framework construindo o **Neogen** — um ERP para assistência técnica com ERPNext + app próprio (`ogun`). O objetivo é implementar a listagem de dispositivos (Celular, Notebook) no formulário do Cliente *e* entender por que cada coisa funciona do jeito que funciona.

---

## Visão Geral: O Que Vamos Construir

Ao abrir um registro de **Customer** no seu site (`neogen.erp.localhost`), você quer ver algo assim:

```
┌─────────────────────────────────────────┐
│  Cliente: João da Silva                 │
│  ...campos normais do Customer...       │
│                                         │
│  ─── Dispositivos Registrados ───       │
│  Tipo      | ID        | Marca | Status │
│  Celular   | CEL-00001 | Apple | Ativo  │
│  Notebook  | NOTE-0012 | Dell  | Ativo  │
└─────────────────────────────────────────┘
```

Para chegar lá, você vai fazer **três coisas independentes** que se completam:

1. **`hooks.py`** → diz ao Frappe que o seu app `ogun` tem algo a acrescentar ao dashboard do Customer
2. **Customize Form** → adiciona campos HTML/Section ao Customer (onde a lista vai aparecer)
3. **Client Script** → o código JavaScript que busca e renderiza os dispositivos

Cada uma dessas três partes resolve um problema diferente. Vamos entender cada uma antes de implementar.

---

## Parte 1 — Sobrescrevendo o Dashboard do Customer via `hooks.py`

### 1.1 O Que É o `hooks.py`?

Pense no `hooks.py` como o arquivo de **configuração de integração** do seu app com o Frappe.

Se você conhece NestJS, pense nele como uma combinação de:
- O `app.module.ts` (declara o que seu módulo oferece)
- Middlewares globais (intercepta comportamentos do framework)
- Event listeners (reage a eventos do sistema)

O `hooks.py` fica na raiz do seu app:

```
ogun/
├── hooks.py          ← aqui
├── modules.txt
├── ogun/
│   ├── doctype/
│   │   ├── celular/
│   │   └── notebook/
│   └── utils/
│       └── customer_dashboard.py
└── ...
```

O Frappe lê esse arquivo na inicialização e registra tudo que seu app "assina". Você nunca chama `hooks.py` diretamente — ele é declarativo, como um manifesto.

---

### 1.2 Por Que Precisamos Sobrescrever o Dashboard?

O **dashboard** de um DocType no Frappe é aquela seção que aparece no topo do formulário mostrando contadores de documentos relacionados. Por exemplo, no Customer nativo do ERPNext você vê:

```
[ Quotations: 3 ]  [ Sales Orders: 12 ]  [ Invoices: 8 ]
```

Cada item desse é um DocType relacionado ao Customer. O ERPNext configura esses links no arquivo `customer_dashboard.py` *dentro do próprio ERPNext*. Você não quer (e não deve) editar esse arquivo — ele é do ERPNext, não do seu app.

O Frappe tem um hook chamado `override_doctype_dashboards` exatamente para isso: permite que um app externo **substitua** a função que define o dashboard de qualquer DocType, sem tocar no código original.

**Conceito de Engenharia Aplicado: Open/Closed Principle**  
O sistema é aberto para extensão (você pode adicionar comportamentos) mas fechado para modificação (você não precisa editar o código original). O hook é o mecanismo de extensão.

---

### 1.3 Implementando

#### Passo 0: Verificar o diretório `utils/` (pré-requisito)

Antes de criar o arquivo, certifique-se de que o diretório `ogun/utils/` existe e **contém um arquivo `__init__.py`** vazio:

```
ogun/
├── utils/
│   ├── __init__.py    ← arquivo vazio (IMPORTANTE)
│   └── customer_dashboard.py  ← vamos criar agora
└── ...
```

Se não existir, crie o arquivo vazio pelo terminal:

```bash
touch ogun/utils/__init__.py
```

**Por que?** Python precisa que todo diretório seja marcado como pacote com um `__init__.py` para que o Frappe consiga importar os módulos dentro dele. Sem esse arquivo, você recebe `ModuleNotFoundError: No module named 'ogun.utils'`.

---

#### Passo 1: Criar o arquivo `customer_dashboard.py` no seu app

```python
# ogun/utils/customer_dashboard.py

def get_data(data=None):
    """
    Estende o dashboard do Customer com um grupo de Dispositivos.
    
    O Frappe passa os dados originais do dashboard via argumento 'data'.
    Nosso trabalho é estender esse dicionário, não substituir.
    """
    # Se data for None (primeira execução), cria um dicionário vazio
    data = data or {}
    
    # Garante que a chave 'transactions' existe
    if "transactions" not in data:
        data["transactions"] = []
    
    # Adiciona (estende) um novo grupo ao dashboard existente
    data["transactions"].append({
        "label": "Dispositivos",
        "items": ["Celular", "Notebook"]   # adicione "PC" quando criar o DocType
    })
    
    return data
```

**O que mudou?**

- A função agora **aceita o parâmetro `data`** — os dados originais do dashboard
- Ao invés de retornar um dicionário novo, a função **estende** os dados existentes
- Isso garante que o dashboard do Customer mantém os dados do ERPNext (Quotations, Sales Orders, etc.) enquanto adiciona o grupo Dispositivos

**O que esse dicionário significa?**

- `transactions` → lista de grupos que aparecem no dashboard
- `label` → o nome do grupo (aparece como título da seção)
- `items` → lista de DocTypes que fazem parte do grupo

O Frappe vai procurar, em cada DocType listado, um campo do tipo `Link` apontando para `Customer`. Quando encontrar, exibe o contador automaticamente.

**Por que funciona?** O Frappe faz uma query do tipo:
```sql
SELECT COUNT(*) FROM `tabCelular` WHERE customer = 'CUST-00001'
```
...e exibe o resultado no botão do dashboard. Ele sabe qual campo usar porque o campo tem `options: "Customer"` na definição.

**⚠️ Importante — Padronização de Fieldnames**  
Todos os DocTypes de dispositivo (Celular, Notebook, PC, etc.) **devem usar o mesmo fieldname** para o link com Customer. Recomendamos `customer` (em inglês, por convenção Frappe).

Se você criou o Celular com fieldname `customer` mas o Notebook com `cliente_responsavel`, edite os arquivos `.json` ou a UI do DocType para padronizar. Isso evita erros como `Unknown column 'tabNotebook.customer' in 'WHERE'` quando o Frappe tenta fazer a contagem.

---

#### Passo 2: Registrar no `hooks.py`

```python
# ogun/hooks.py

app_name = "ogun"
app_title = "Ogun"
# ... outros campos já existentes ...

override_doctype_dashboards = {
    "Customer": "ogun.utils.customer_dashboard.get_data"
}
```

O valor é uma **string com o caminho Python completo** para a função — como um import path. O Frappe vai chamar `ogun.utils.customer_dashboard.get_data()` sempre que precisar renderizar o dashboard do Customer, passando os dados originais como argumento.

---

#### Passo 3: Aplicar as mudanças no site

Sempre que você alterar o `hooks.py` ou arquivos Python do app, precisa reiniciar o servidor:

```bash
# No diretório frappe-bench
bench restart
```

Se quiser ser mais específico (reinicia só o worker Python, não o Redis):
```bash
bench --site neogen.erp.localhost migrate
bench restart
```

**Como testar:** Abra qualquer Customer no seu site. No topo do formulário, deve aparecer um grupo "Dispositivos" com os contadores de Celular e Notebook. Se um Customer não tiver nenhum dispositivo, o contador fica em zero mas o botão ainda aparece.

**Se receber erros na abertura do Customer:**

1. **`ModuleNotFoundError: No module named 'ogun.utils'`** → Você não criou o arquivo `__init__.py` no diretório `ogun/utils/`. Volte ao Passo 0.

2. **`TypeError: get_data() got an unexpected keyword argument 'data'`** → Sua função não aceita o argumento `data`. Certifique-se de que a assinatura é `def get_data(data=None):` (veja o exemplo acima).

3. **`Unknown column 'tabNotebook.customer' in 'WHERE'`** → Os fieldnames para link com Customer são inconsistentes entre os DocTypes. Verifique:
   - Celular tem fieldname `customer` ou `cliente`?
   - Notebook tem fieldname `customer` ou `cliente_responsavel`?
   
   **Solução:** Padronize todos para `customer`. Se usar a UI do Frappe (Customize Form), renomeie os campos. Se usar arquivos `.json`, edite-os e aplique as mudanças com `bench migrate`.

---

## Parte 2 — Criando Custom Fields via Customize Form

### 2.1 O Que São Custom Fields?

No Frappe, cada DocType tem um **schema** — a lista de campos que ele possui. Esse schema é armazenado no banco de dados, não só em arquivos.

Quando você cria um DocType próprio (como `Celular`), define os campos em um arquivo `celular.json`. Mas e quando você quer adicionar campos a um DocType que não é seu — como o `Customer` do ERPNext?

Você **não edita** o `customer.json` do ERPNext (isso quebraria updates futuros). Em vez disso, você cria **Custom Fields**: campos extras armazenados separadamente no banco, que o Frappe injeta no formulário em runtime.

**Analogia com NestJS:** É como usar **decorators de extensão** em vez de herdar e sobrescrever uma classe do framework. Você não toca na classe original — você registra metadados extras que o sistema processa automaticamente.

**Conceito de Engenharia Aplicado: Extension without Modification**  
Os Custom Fields são um exemplo de como o Frappe implementa customização não-invasiva. Eles ficam na tabela `tabCustom Field` do banco de dados e são mergeados com o schema original em tempo de execução.

---

### 2.2 Por Que Precisamos de Custom Fields Aqui?

O Client Script (Parte 3) vai renderizar HTML com a lista de dispositivos. Para isso, ele precisa de um **lugar no formulário** para colocar esse HTML. Esse lugar não existe no Customer original — precisamos criá-lo.

Vamos adicionar dois campos:

1. **Section Break** → cria uma seção visual separada no formulário ("Dispositivos Registrados")
2. **HTML** → um campo vazio onde o script vai injetar a tabela de dispositivos

---

### 2.3 Implementando via Customize Form

#### Passo 1: Abrir o Customize Form

No menu superior do ERPNext:

```
Configurações (ícone de engrenagem) → Customize Form
```

Ou acesse diretamente via barra de busca (Ctrl+G):
```
Customize Form
```

#### Passo 2: Selecionar o DocType

No campo "Enter Form Type", digite e selecione:
```
Customer
```

O formulário vai carregar todos os campos atuais do Customer.

#### Passo 3: Adicionar o Section Break

Role até o **final** da lista de campos (ou até onde você quer que a seção apareça) e clique em **"Add Row"**.

Preencha assim:

| Propriedade | Valor |
|---|---|
| Label | `Dispositivos Registrados` |
| Fieldname | `dispositivos_section` |
| Fieldtype | `Section Break` |

**O que é Section Break?**  
Não é um campo que armazena dado — é um elemento visual que divide o formulário em seções com título. Pense nele como um `<hr>` com label no HTML. Todo campo depois de um Section Break fica agrupado visualmente nessa seção.

#### Passo 4: Adicionar o campo HTML

Clique em **"Add Row"** novamente, logo após o Section Break:

| Propriedade | Valor |
|---|---|
| Label | `Dispositivos HTML` |
| Fieldname | `dispositivos_html` |
| Fieldtype | `HTML` |

**O que é um campo HTML no Frappe?**  
É um campo especial que renderiza conteúdo HTML arbitrário. Ele não salva dados no banco — serve como um "slot" de conteúdo dinâmico. O Client Script vai acessar esse campo pelo `fieldname` e injetar HTML nele.

#### Passo 5: Salvar

Clique no botão **"Update"** no topo do Customize Form.

O Frappe vai criar registros na tabela `tabCustom Field` do banco de dados. A partir desse momento, todo formulário de Customer no sistema vai ter esses dois campos.

**Como verificar:** Abra qualquer Customer. Role até o final — você deve ver a seção "Dispositivos Registrados" com um espaço vazio (onde o script vai colocar a tabela).

---

### 2.4 Alternativa para o Futuro: Custom Fields como Fixtures

Criar via UI é ótimo para aprender e testar. Mas em produção, o ideal é versionar esses campos no seu app como **fixtures** — arquivos JSON que o Frappe importa automaticamente.

Quando você quiser fazer isso:

```bash
# Exporta os custom fields do Customer para o seu app
bench --site neogen.erp.localhost export-fixtures
```

E no `hooks.py`:
```python
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["dt", "=", "Customer"]]
    }
]
```

Isso garante que, se você reinstalar o app em outro servidor, os campos aparecem automaticamente. Por ora, via UI está ótimo.

---

## Parte 3 — Criando o Client Script via UI

### 3.1 O Que É um Client Script no Frappe?

No Frappe, **Client Scripts** são códigos JavaScript que rodam no browser, associados a um DocType específico. Eles reagem a eventos do formulário — quando ele abre, quando um campo muda, quando você salva, etc.

Se você vem de React, pense assim:

- O formulário do Frappe é como um componente controlado
- O Client Script é como um conjunto de `useEffect` e event handlers para esse componente
- Os eventos (`refresh`, `onload`, `before_save`) são como os hooks do ciclo de vida

**Onde o Client Script fica armazenado?**  
Ao contrário de arquivos JS em `public/`, o Client Script é um **registro no banco de dados** — um documento do DocType `Client Script`. Quando o browser carrega um formulário de Customer, o Frappe busca no banco todos os Client Scripts associados ao `Customer` e os executa.

Isso significa que você pode criar, editar e testar Client Scripts direto pela UI — sem precisar reiniciar o servidor ou fazer deploy.

**Conceito de Engenharia Aplicado: Data-driven Behavior**  
O comportamento do frontend é configurado via dados (registros no banco), não só via código em arquivos. Isso permite customização em runtime sem deploy — o mesmo princípio de feature flags e configuração dinâmica.

---

### 3.2 Por Que Um Client Script e Não um Arquivo JS?

Você poderia colocar código JavaScript em `ogun/public/js/customer.js` e registrar no `hooks.py`. Isso também funciona. Mas para scripts de customização de formulário, o Frappe recomenda Client Scripts porque:

1. **Visibilidade**: você vê e edita pelo UI, sem precisar de acesso ao servidor
2. **Isolamento**: o script fica associado explicitamente a um DocType
3. **Reload automático**: mudanças aparecem sem `bench build`

Em projetos maiores, scripts complexos costumam ir para arquivos (melhor para versionamento com Git). Para o que vamos fazer, Client Script via UI é perfeito.

---

### 3.3 Implementando

#### Passo 1: Navegar até Client Script

Na barra de busca (Ctrl+G) do ERPNext, busque:
```
Client Script
```

Clique em **"New Client Script"**.

#### Passo 2: Configurar o Script

Preencha os campos:

| Campo | Valor |
|---|---|
| **DocType** | `Customer` |
| **Apply To** | `Form` |
| **Enabled** | ✅ (marcado) |

O campo **"Apply To"** define o contexto. `Form` significa que o script roda quando um formulário de Customer está aberto. A alternativa seria `List` (para a listagem de registros).

#### Passo 3: Escrever o Script

No campo de código, cole o seguinte:

```javascript
// ─── Evento principal: roda sempre que o formulário é carregado/atualizado ───
frappe.ui.form.on("Customer", {
    refresh(frm) {
        // Só roda se o Customer já foi salvo (tem um nome/ID)
        // frm.doc.name é null em documentos novos ainda não salvos
        if (!frm.doc.name) return;

        renderDispositivos(frm);
    }
});

// ─── Função principal: busca e renderiza a lista de dispositivos ───
async function renderDispositivos(frm) {
    // Define quais DocTypes de dispositivo existem
    // Quando criar PC, adicione "PC" aqui
    const tiposDeDispositivo = ["Celular", "Notebook"];

    // frappe.db.get_list faz uma requisição GET para a API REST do Frappe:
    // GET /api/resource/Celular?filters=[["customer","=","CUST-00001"]]&fields=["name","marca",...]
    //
    // ⚠️ IMPORTANTE: O fieldname 'customer' aqui deve corresponder ao fieldname real
    // no seu DocType. Se você usou 'cliente' ou 'cliente_responsavel', mude aqui também.
    // Para manter compatibilidade com Frappe, recomendamos usar 'customer' em todos.
    //
    // Promise.all executa todas as buscas em paralelo (como Promise.all no Node)
    // e espera todas terminarem antes de continuar
    const consultas = tiposDeDispositivo.map(tipo =>
        frappe.db.get_list(tipo, {
            filters: { customer: frm.doc.name },
            fields: ["name", "marca", "modelo", "numero_serie", "status"],
            limit: 100
        })
        // Após cada busca, anexa o tipo ao resultado para saber a origem
        .then(registros => registros.map(r => ({ ...r, _tipo: tipo })))
    );

    const resultados = await Promise.all(consultas);

    // .flat() junta o array de arrays em um array único
    // Ex: [["cel1", "cel2"], ["note1"]] → ["cel1", "cel2", "note1"]
    const dispositivos = resultados.flat();

    // Referência ao wrapper do campo HTML que criamos no Customize Form
    const $wrapper = frm.get_field("dispositivos_html").$wrapper;

    // ─── Caso: nenhum dispositivo encontrado ───
    if (!dispositivos.length) {
        $wrapper.html(`
            <p class="text-muted" style="padding: 10px 0;">
                Nenhum dispositivo registrado para este cliente.
            </p>
        `);
        return;
    }

    // ─── Caso: dispositivos encontrados ───
    // Gera uma linha <tr> para cada dispositivo
    const linhas = dispositivos.map(d => {
        // Monta a URL do formulário do dispositivo
        // Ex: /app/celular/CEL-00001
        const url = `/app/${d._tipo.toLowerCase()}/${d.name}`;

        // Badge de status com cor condicional
        const corStatus = d.status === "Ativo" ? "green" : "gray";

        return `
            <tr>
                <td>${d._tipo}</td>
                <td><a href="${url}">${d.name}</a></td>
                <td>${d.marca || "—"}</td>
                <td>${d.modelo || "—"}</td>
                <td>${d.numero_serie || "—"}</td>
                <td>
                    <span class="indicator-pill ${corStatus}">
                        ${d.status || "—"}
                    </span>
                </td>
            </tr>
        `;
    }).join("");

    // Injeta a tabela completa no campo HTML
    $wrapper.html(`
        <div style="margin-top: 10px;">
            <table class="table table-bordered table-sm">
                <thead class="grid-heading-row">
                    <tr>
                        <th>Tipo</th>
                        <th>ID</th>
                        <th>Marca</th>
                        <th>Modelo</th>
                        <th>Nº de Série</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${linhas}
                </tbody>
            </table>
        </div>
    `);
}
```

#### Passo 4: Salvar o Client Script

Clique em **Save** (ou Ctrl+S).

Não precisa reiniciar nada. O script passa a valer imediatamente para qualquer sessão que abrir um Customer a partir de agora.

---

### 3.4 Entendendo o `frappe.db.get_list`

Você vem de um mundo onde faz `axios.get('/api/devices?customer=X')`. O `frappe.db.get_list` é essencialmente isso — uma abstração de alto nível sobre a API REST do Frappe.

Por baixo dos panos, ele faz:

```
GET /api/resource/Celular
    ?filters=[["cliente","=","CUST-00001"]]
    &fields=["name","marca","modelo","numero_serie","status"]
    &limit=100
```

Você pode testar essa URL diretamente no browser (estando logado no ERPNext) para ver o JSON que retorna. Isso é útil para debugar.

**Por que `frappe.db` e não `fetch` direto?**  
`frappe.db` cuida de autenticação (CSRF token), URL base, serialização dos filtros e tratamento de erros automaticamente. É a camada de abstração recomendada para scripts de formulário.

---

## Parte 4 — Verificando Que Tudo Funciona

### Checklist de verificação

#### 4.1 Verificar o Dashboard (Parte 1)

1. Abra qualquer Customer no ERPNext
2. No topo do formulário, procure os botões de contagem
3. Você deve ver um grupo **"Dispositivos"** com botões para Celular e Notebook
4. Se tiver um Customer com dispositivos cadastrados, os contadores devem mostrar o número correto

**Se não aparecer ou receber erro:** Verifique os seguintes problemas comuns (nesta ordem):

**Erro: `ModuleNotFoundError: No module named 'ogun.utils'`**
- Certifique-se de que existe um arquivo `ogun/utils/__init__.py` (pode estar vazio)
- Se não existir, crie com: `touch ogun/utils/__init__.py`
- Execute `bench restart` após criar

**Erro: `TypeError: get_data() got an unexpected keyword argument 'data'`**
- Sua função não está aceitando o argumento `data`
- Corrija a assinatura para: `def get_data(data=None):`
- E certifique-se de que a função estende `data` ao invés de substituir (veja o exemplo no Passo 1)

**Erro: `Unknown column 'tabNotebook.customer' in 'WHERE'`** ou similar
- Os fieldnames para link com Customer são inconsistentes entre DocTypes
- Verifique: Celular usa `customer` mas Notebook usa `cliente_responsavel`?
- **Solução:** Padronize todos os DocTypes para usar `customer` como fieldname
  - Via UI: Vá a Customize Form do Notebook, renomeie `cliente_responsavel` para `customer`, salve
  - Via arquivo: Edite o `.json` do DocType, renomeie o field, execute `bench migrate`

**Verificação básica:** Execute `bench restart` e recarregue a página com Ctrl+Shift+R (force refresh). Verifique se o caminho no `hooks.py` está correto (`ogun.utils.customer_dashboard.get_data`).

#### 4.2 Verificar os Custom Fields (Parte 2)

1. Abra qualquer Customer
2. Role até o final do formulário
3. Você deve ver a seção **"Dispositivos Registrados"**
4. Por enquanto o espaço está vazio — o script ainda não rodou (ou rodou e não encontrou dispositivos)

**Se não aparecer:** Volte ao Customize Form e confirme que os campos foram salvos. Recarregue a página com Ctrl+Shift+R (force refresh).

#### 4.3 Verificar o Client Script (Parte 3)

1. Abra um Customer que tenha pelo menos um Celular ou Notebook com o campo `customer` preenchido com o nome desse Customer
   - ⚠️ **Importante:** Certifique-se de que todos os DocTypes de dispositivo usam `customer` (não `cliente` ou `cliente_responsavel`) como fieldname para link com Customer
   - Se tiver usado nomes diferentes, renomeie-os para `customer` ou atualize o filtro no Client Script
2. Na seção "Dispositivos Registrados", deve aparecer a tabela com os dispositivos
3. Os IDs na coluna "ID" devem ser links clicáveis que abrem o formulário do dispositivo

**Se a tabela não aparecer:**

Abra o Console do Browser (F12 → Console) e procure por erros em vermelho. Os mais comuns são:

```
fieldname 'dispositivos_html' not found
```
→ O Custom Field não foi salvo. Volte ao Customize Form e confirme.

```
frappe.db.get_list is not a function
```
→ Verifique se você está no contexto de um Form (não List).

```
(sem erro, mas tabela vazia)
```
→ Possíveis causas:
  1. O fieldname para link com Customer nos DocTypes não é `customer` — verifique qual é (pode ser `cliente`, `cliente_responsavel`, etc.)
  2. Nenhum Customer tem dispositivos com o fieldname correto preenchido
  3. **Solução:** Se usar fieldname diferente de `customer`, edite o Client Script (Passo 3.3) e mude a linha:
     ```javascript
     filters: { cliente: frm.doc.name },
     ```
     para:
     ```javascript
     filters: { cliente_responsavel: frm.doc.name },  // ou o fieldname que usar
     ```
  4. **Melhor solução:** Padronize todos os DocTypes para usar `customer` como fieldname — assim não precisa editar o script

---

## Parte 5 — Recapitulando a Arquitetura

Você acabou de implementar um padrão que aparece muito em sistemas extensíveis. Veja como as três partes se encaixam:

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Frontend)                       │
│                                                             │
│  Formulário Customer carrega                                │
│       ↓                                                     │
│  Frappe busca Client Scripts do Customer no banco           │
│       ↓                                                     │
│  Executa: refresh() → renderDispositivos()                  │
│       ↓                                                     │
│  frappe.db.get_list("Celular", ...) ──→ GET /api/resource/  │
│  frappe.db.get_list("Notebook", ...) ─→ GET /api/resource/  │
│       ↓                                                     │
│  Injeta HTML no campo dispositivos_html                     │
└─────────────────────────────────────────────────────────────┘
         ↑                        ↑
         │                        │
┌────────┴──────────┐   ┌────────┴──────────┐
│   hooks.py        │   │  Customize Form    │
│                   │   │                   │
│  Registra que     │   │  Criou o "espaço" │
│  ogun contribui   │   │  no formulário    │
│  ao dashboard     │   │  (dispositivos_   │
│  do Customer      │   │   html)           │
└───────────────────┘   └───────────────────┘
```

**Três responsabilidades separadas:**

| Peça | Responsabilidade | Onde fica |
|---|---|---|
| `hooks.py` | Integração app ↔ framework | Arquivo Python no `ogun` |
| Custom Fields | Estrutura do formulário | Banco de dados (via UI) |
| Client Script | Comportamento do frontend | Banco de dados (via UI) |

Essa separação é intencional — cada peça pode mudar independentemente sem quebrar as outras.

---

## Próximos Passos Sugeridos

Agora que isso está funcionando, algumas evoluções naturais:

**1. Adicionar o DocType `PC`**  
Quando criar, só precisa adicionar `"PC"` em dois lugares: no `customer_dashboard.py` e no array `tiposDeDispositivo` do Client Script.

**2. Versionando com fixtures**  
Exporte os Custom Fields como fixtures para que o ambiente de produção se configure automaticamente com `bench migrate`.

**3. Botão "Adicionar Dispositivo"**  
No Client Script, você pode adicionar um botão na seção que abre o formulário de novo Celular/Notebook já com o campo `cliente` preenchido:

```javascript
frm.add_custom_button("Novo Celular", () => {
    frappe.new_doc("Celular", { cliente: frm.doc.name });
}, "Dispositivos");
```

**4. Filtro por status**  
Adicionar um dropdown que filtra a tabela por status (Ativo, Em Manutenção, Inativo) — tudo client-side sem nova requisição, só filtrando o array `dispositivos` já carregado.
