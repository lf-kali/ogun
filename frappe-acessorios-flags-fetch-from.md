# Modelagem de Atributos Variáveis no Frappe: Flags em DocType Mestre + `fetch_from` em Child Table

> **Perfil de audiência:** `frappe-dev` — desenvolvedor com background em NestJS/React/Python, aprendendo Frappe Framework no projeto Ogun (assistência técnica)
> **Nível:** Intermediário
> **Tempo estimado:** 2–3 horas (implementação + leitura dos conceitos)

---

## Visão Geral

No sistema Ogun, cada Ordem de Serviço precisa registrar os acessórios que o cliente entregou junto com o aparelho — cabo, carregador, capinha, cartão de memória, mouse, teclado, e assim por diante. O desafio é que cada tipo de acessório tem propriedades diferentes: um carregador tem padrão de tomada e wattagem, um cartão de memória tem capacidade e classe de velocidade, uma capinha não tem nenhuma dessas propriedades.

Esse é o problema clássico de **atributos variáveis por entidade** — uma das situações mais recorrentes em modelagem de dados. Neste guia vamos implementar a solução mais robusta para o Frappe: um DocType mestre (`Tipo Acessório`) que declara, via campos booleanos (flags), quais propriedades se aplicam a cada tipo, e um DocType filho (`Acessório Cliente`) que usa `fetch_from` para buscar essas flags e `depends_on` para exibir os campos certos no formulário.

Ao final, você terá:
- `Tipo Acessório`: cadastro configurável de tipos com suas flags de propriedades
- `Acessório Cliente`: child table da Ordem de Serviço com campos condicionais
- Um Client Script que garante reatividade em tempo real ao selecionar o tipo
- Compreensão sólida dos padrões arquiteturais usados no Frappe

---

## Conceitos-Chave

Antes de abrir o terminal, você precisa internalizar quatro conceitos. Não pule esta seção — ela é o mapa que torna o passo a passo compreensível.

### 1. DocType Mestre vs. DocType Filho (Child Table)

No Frappe, existem dois papéis estruturalmente distintos para um DocType:

**DocType Mestre (ou independente):** tem sua própria lista, seu próprio formulário, e seus próprios registros persistidos na tabela correspondente no banco. Você acessa ele via menu de módulo ou via Link. Exemplos: `Customer`, `Item`, `Supplier`. No seu projeto: `Tipo Acessório`.

**DocType Filho (Child Table):** não existe sozinho. Ele só existe como parte de outro DocType, dentro de um campo do tipo `Table`. Não tem lista própria, e seus registros ficam em uma tabela com sufixo no banco (ex: `tabAcessório Cliente`), mas sempre referenciando o documento pai. No seu projeto: `Acessório Cliente`, que vive dentro de `Ordem de Serviço`.

A analogia com o que você conhece: se `Ordem de Serviço` fosse uma entidade NestJS, `Acessório Cliente` seria uma entidade com `@ManyToOne` apontando para ela — exceto que no Frappe isso é configuração, não código de entidade.

### 2. Campo `Link`

Um campo do tipo `Link` no Frappe é o equivalente a uma foreign key. Ele aponta para um DocType mestre e armazena o `name` do registro referenciado (no Frappe, `name` é sempre a chave primária — por padrão é o título do registro ou um ID gerado). Quando você seleciona "Carregador" num campo `Link → Tipo Acessório`, o Frappe armazena a string `"Carregador"` no banco, que é o `name` daquele registro.

### 3. Campo `fetch_from`

`fetch_from` é uma propriedade de campo que instrui o Frappe a copiar automaticamente o valor de um campo de outro DocType a partir de um Link. A sintaxe é `nome_do_campo_link.nome_do_campo_no_doctype_alvo`.

**Exemplo:** se `Acessório Cliente` tem um campo `tipo_acessorio` (Link → Tipo Acessório) e um campo `_tem_padrao_tomada` com `fetch_from = tipo_acessorio.tem_padrao_tomada`, quando você selecionar "Carregador" no campo `tipo_acessorio`, o Frappe vai buscar o valor de `tem_padrao_tomada` no registro "Carregador" de `Tipo Acessório` e copiar para `_tem_padrao_tomada` na linha atual.

**Limitação crítica:** por padrão, `fetch_from` roda ao salvar o documento, não ao mudar o campo em tempo real. Veremos como contornar isso com um Client Script.

### 4. Campo `depends_on`

`depends_on` é uma expressão JavaScript avaliada pelo Frappe para decidir se um campo deve ser **visível** (e obrigatório, se marcado como tal). A expressão tem acesso ao objeto `doc`, que no contexto de uma child table representa a linha atual.

**Exemplo:** `eval:doc.tem_padrao_tomada == 1` faz o campo aparecer somente se `tem_padrao_tomada` for verdadeiro na linha atual.

Combinando `fetch_from` (que popula as flags) com `depends_on` (que lê as flags para mostrar/ocultar campos), você cria um formulário dinâmico sem escrever lógica de visibilidade no código — é configuração pura que o Frappe interpreta.

### 5. O Padrão Arquitetural: Feature Flags em Entidade Mestre

O que estamos implementando é uma variação do padrão **Feature Flags** aplicado a metadados. Em vez de flags que ativam funcionalidades de software, são flags que ativam **propriedades de uma entidade de domínio**. O DocType mestre (`Tipo Acessório`) funciona como um **schema dinâmico declarativo** — ele descreve a estrutura de dados dos registros filhos sem que você precise criar tabelas ou campos separados para cada variação.

Isso aplica o princípio **Open/Closed** (do SOLID): o sistema está aberto para extensão (você adiciona um novo tipo de acessório sem alterar código) e fechado para modificação (a estrutura do `Acessório Cliente` não muda quando novos tipos surgem).

---

## Pré-requisitos

- [ ] ERPNext instalado e rodando localmente (`bench start` funcionando)
- [ ] App próprio criado (`bench new-app ogun` já executado)
- [ ] Módulo criado dentro do app Ogun (ex: `Atendimento`)
- [ ] Acesso ao painel de administrador do site (`/app/doctype`)
- [ ] Familiaridade básica com o formulário de DocType no Frappe (saber criar campos)
- [ ] Entendimento de que `name` no Frappe é a chave primária de cada registro

---

## Sumário

1. [Criar o DocType `Tipo Acessório`](#1-criar-o-doctype-tipo-acessório)
2. [Cadastrar os tipos iniciais e suas flags](#2-cadastrar-os-tipos-iniciais-e-suas-flags)
3. [Criar o DocType `Acessório Cliente`](#3-criar-o-doctype-acessório-cliente)
4. [Adicionar o campo `Table` na Ordem de Serviço](#4-adicionar-o-campo-table-na-ordem-de-serviço)
5. [Escrever o Client Script para reatividade em tempo real](#5-escrever-o-client-script-para-reatividade-em-tempo-real)
6. [Testar o fluxo completo](#6-testar-o-fluxo-completo)
7. [Exportar os fixtures para versionamento](#7-exportar-os-fixtures-para-versionamento)

---

## 1. Criar o DocType `Tipo Acessório`

### O que é / O que vamos fazer

`Tipo Acessório` é o **DocType mestre** — o catálogo de referência. Ele vai armazenar registros como "Carregador", "Cabo", "Capinha", e para cada um, declarar via checkboxes quais propriedades fazem sentido. É a fonte da verdade sobre o que cada tipo de acessório "sabe" sobre si mesmo.

Pense nele como um schema de configuração, não como dados transacionais. Ele muda raramente (quando você adiciona um novo tipo de acessório ao negócio) e é reutilizado em todas as ordens de serviço.

### Por que dessa forma?

Centralizar as regras de propriedade no mestre segue o princípio **Single Source of Truth**: existe exatamente um lugar onde está definido que "Carregador tem padrão de tomada". Se amanhã você decidir que carregadores também precisam registrar wattagem, você adiciona uma flag `tem_wattagem` uma vez no DocType e a lógica se propaga automaticamente para todos os formulários.

A alternativa (hardcodar os nomes dos tipos nas expressões `depends_on` do filho) quebra esse princípio — a regra fica distribuída pelo schema do filho, invisível e difícil de rastrear.

### Passo a Passo

#### Passo 1 — Acessar a criação de DocType

No painel do Frappe, vá em:

```
Menu lateral → [seu módulo] → DocType List → New
```

Ou acesse diretamente: `http://neogen-erp-v0.1.local/app/doctype/new-doctype`

#### Passo 2 — Configurar as propriedades básicas do DocType

Preencha o formulário de criação do DocType com:

| Campo | Valor |
|---|---|
| **Name** | `Tipo Acessório` |
| **Module** | `Ogun` (ou o nome do seu módulo) |
| **Is Submittable** | ❌ desmarcado |
| **Is Child Table** | ❌ desmarcado — este é um mestre |
| **Quick Entry** | ✅ marcado — facilita cadastro rápido pelo modal |
| **Search Fields** | `name` (padrão) |

> 💡 **Nota:** O campo "Name" do DocType define tanto o nome da tabela no banco (`tabTipo Acessório`) quanto o identificador usado em campos `Link` de outros DocTypes. Use exatamente `Tipo Acessório` com acento — o Frappe lida bem com isso.

#### Passo 3 — Adicionar os campos de identidade

Adicione os campos na aba **Fields** do formulário de DocType:

**Campo 1 — Nome do tipo** (já existe por padrão como o campo title):
O Frappe cria automaticamente o campo `name` como chave primária. Por padrão em DocTypes sem autoname customizado, o `name` é preenchido pelo usuário — ou seja, o nome que você digitar ao criar "Carregador" será a PK e o valor usado nos Links. Isso é o comportamento correto aqui.

**Campo 2 — Categoria** (opcional mas recomendado):

```
Field Type: Select
Field Name: categoria
Label: Categoria
Options:
  Alimentação
  Conectividade
  Proteção
  Armazenamento
  Periférico
  Outro
```

Isso vai facilitar filtros e relatórios futuros ("todos os acessórios de Alimentação entregues esta semana").

**Campo 3 — Seção de flags** (separador visual):

```
Field Type: Section Break
Label: Propriedades Aplicáveis
```

Seções no Frappe são apenas separadores visuais — não armazenam dado, mas organizam o formulário. Isso é análogo a um `<fieldset>` em HTML.

**Campo 4 em diante — As flags booleanas:**

Para cada propriedade possível entre todos os tipos de acessório, crie um campo `Check`:

```
Field Type: Check
Field Name: tem_padrao_tomada
Label: Tem padrão de tomada?
Default: 0
```

```
Field Type: Check
Field Name: tem_tipo_conector
Label: Tem tipo de conector?
Default: 0
```

```
Field Type: Check
Field Name: tem_wattagem
Label: Tem wattagem?
Default: 0
```

```
Field Type: Check
Field Name: tem_capacidade
Label: Tem capacidade?
Default: 0
```

```
Field Type: Check
Field Name: tem_classe_velocidade
Label: Tem classe de velocidade?
Default: 0
```

```
Field Type: Check
Field Name: tem_conectividade_sem_fio
Label: Tem conectividade sem fio?
Default: 0
```

```
Field Type: Check
Field Name: tem_layout
Label: Tem layout? (para teclados)
Default: 0
```

> 💡 **Nota sobre nomenclatura:** o prefixo `tem_` é uma convenção semântica — esses campos respondem a perguntas booleanas ("este tipo tem tal propriedade?"). Você poderia usar `has_` em inglês se preferir padronizar o projeto em inglês. Escolha um padrão e mantenha.

#### Passo 4 — Salvar o DocType

Clique em **Save**. O Frappe vai:
1. Criar a tabela `tabTipo Acessório` no banco MariaDB
2. Registrar o DocType no sistema de metadados (`tabDocType`)
3. Tornar `Tipo Acessório` disponível como opção em campos `Link`

---

## 2. Cadastrar os tipos iniciais e suas flags

### O que é / O que vamos fazer

Com o DocType criado, precisamos popular o catálogo com os tipos de acessório reais. Cada registro é uma instância de `Tipo Acessório`, e o conjunto de flags marcadas define quais propriedades serão exibidas no formulário da Ordem de Serviço quando aquele tipo for selecionado.

### Por que dessa forma?

Esta etapa concretiza o valor da arquitetura: a configuração acontece em dados, não em código. Um analista de negócio poderia fazer isso sem tocar em nenhuma linha de Python ou JavaScript — só precisa de acesso ao módulo de cadastro.

### Passo a Passo

#### Passo 1 — Acessar a lista de Tipo Acessório

```
Menu lateral → Ogun → Tipo Acessório → New
```

#### Passo 2 — Criar os registros

Crie um registro para cada tipo, marcando as flags correspondentes:

**Carregador:**
```
Name: Carregador
Categoria: Alimentação
tem_padrao_tomada: ✅
tem_tipo_conector: ✅
tem_wattagem: ✅
```

**Cabo:**
```
Name: Cabo
Categoria: Conectividade
tem_tipo_conector: ✅
(wattagem não se aplica a cabo standalone)
```

**Capinha:**
```
Name: Capinha
Categoria: Proteção
(nenhuma flag marcada — só cor e detalhes livres)
```

**Cartão de Memória:**
```
Name: Cartão de Memória
Categoria: Armazenamento
tem_capacidade: ✅
tem_classe_velocidade: ✅
tem_tipo_conector: ✅ (SD, microSD, CF, CFexpress)
```

**Fone de Ouvido:**
```
Name: Fone de Ouvido
Categoria: Periférico
tem_tipo_conector: ✅
tem_conectividade_sem_fio: ✅
```

**Mouse:**
```
Name: Mouse
Categoria: Periférico
tem_tipo_conector: ✅
tem_conectividade_sem_fio: ✅
```

**Teclado:**
```
Name: Teclado
Categoria: Periférico
tem_tipo_conector: ✅
tem_conectividade_sem_fio: ✅
tem_layout: ✅
```

**HD / SSD Externo:**
```
Name: HD Externo
Categoria: Armazenamento
tem_capacidade: ✅
tem_tipo_conector: ✅
```

**Pen Drive:**
```
Name: Pen Drive
Categoria: Armazenamento
tem_capacidade: ✅
tem_tipo_conector: ✅
```

**Power Bank:**
```
Name: Power Bank
Categoria: Alimentação
tem_capacidade: ✅
tem_wattagem: ✅
tem_tipo_conector: ✅
```

> 💡 **Nota:** estes registros são seus **fixtures** — dados de configuração que fazem parte do sistema, não dados de negócio do cliente. Mais adiante veremos como exportá-los para o repositório Git do app Ogun.

---

## 3. Criar o DocType `Acessório Cliente`

### O que é / O que vamos fazer

`Acessório Cliente` é o **DocType filho** — a child table que vai aparecer como tabela dentro do formulário da Ordem de Serviço. Cada linha representa um acessório específico entregue pelo cliente. Ele tem:

- Um campo `Link` para `Tipo Acessório` (o que é o acessório)
- Campos de flag ocultos (`fetch_from`) que copiam as flags do tipo selecionado
- Campos de propriedade reais (`depends_on`) que aparecem condicionalmente baseados nas flags
- Campo de cor e detalhes livres

### Por que dessa forma?

A separação entre "campos de flag" (ocultos, prefixo `_`) e "campos de propriedade" (visíveis) é uma aplicação de **Separation of Concerns** dentro do próprio DocType: os campos prefixados com `_` são infraestrutura de apresentação — eles existem para servir o `depends_on`, não para serem lidos pelo usuário ou pelo código de negócio. Os campos de propriedade são o dado real.

Esta convenção de prefixo `_` é importante porque comunica intenção para qualquer desenvolvedor que abrir este DocType no futuro: "este campo não é dado de negócio, é mecanismo interno".

### Passo a Passo

#### Passo 1 — Criar o DocType com as configurações de filho

```
Menu lateral → DocType List → New
```

| Campo | Valor |
|---|---|
| **Name** | `Acessório Cliente` |
| **Module** | `Ogun` |
| **Is Child Table** | ✅ marcado — fundamental |
| **Is Submittable** | ❌ |
| **Editable Grid** | ✅ marcado — permite editar diretamente na linha da tabela sem abrir modal |

> 💡 **Sobre `Is Child Table`:** marcar este checkbox faz o Frappe tratar este DocType como filho. Ele some das listas de menu, não tem rota própria, e seus registros só existem atrelados a um documento pai. No banco, a tabela terá uma coluna `parent` (o `name` da Ordem de Serviço), `parenttype` (`"Ordem de Serviço"`) e `parentfield` (o nome do campo `Table` no pai).

#### Passo 2 — Adicionar o campo de link para o tipo

```
Field Type: Link
Field Name: tipo_acessorio
Label: Tipo de Acessório
Options: Tipo Acessório
Required: ✅
In List View: ✅
```

`In List View` faz essa coluna aparecer na visualização compacta da tabela, sem precisar abrir cada linha.

#### Passo 3 — Adicionar os campos de flag ocultos (`fetch_from`)

Para cada flag em `Tipo Acessório`, crie um campo correspondente em `Acessório Cliente`:

```
Field Type: Check
Field Name: _tem_padrao_tomada
Label: _tem_padrao_tomada
fetch_from: tipo_acessorio.tem_padrao_tomada
Hidden: ✅
Print Hide: ✅
```

```
Field Type: Check
Field Name: _tem_tipo_conector
Label: _tem_tipo_conector
fetch_from: tipo_acessorio.tem_tipo_conector
Hidden: ✅
Print Hide: ✅
```

```
Field Type: Check
Field Name: _tem_wattagem
Label: _tem_wattagem
fetch_from: tipo_acessorio.tem_wattagem
Hidden: ✅
Print Hide: ✅
```

```
Field Type: Check
Field Name: _tem_capacidade
Label: _tem_capacidade
fetch_from: tipo_acessorio.tem_capacidade
Hidden: ✅
Print Hide: ✅
```

```
Field Type: Check
Field Name: _tem_classe_velocidade
Label: _tem_classe_velocidade
fetch_from: tipo_acessorio.tem_classe_velocidade
Hidden: ✅
Print Hide: ✅
```

```
Field Type: Check
Field Name: _tem_conectividade_sem_fio
Label: _tem_conectividade_sem_fio
fetch_from: tipo_acessorio.tem_conectividade_sem_fio
Hidden: ✅
Print Hide: ✅
```

```
Field Type: Check
Field Name: _tem_layout
Label: _tem_layout
fetch_from: tipo_acessorio.tem_layout
Hidden: ✅
Print Hide: ✅
```

> 💡 **Por que `Print Hide`?** Marcar `Print Hide` garante que esses campos internos não apareçam em nenhum template de impressão da Ordem de Serviço. São detalhes de implementação, não informação para o cliente ou técnico.

> 💡 **Sobre `fetch_from` e o banco:** os campos com `fetch_from` ainda são persistidos no banco normalmente — o Frappe simplesmente os preenche automaticamente. Isso é intencional: significa que você pode fazer queries SQL ou relatórios usando esses campos se necessário, sem precisar fazer join com `Tipo Acessório` em cada consulta.

#### Passo 4 — Adicionar os campos de propriedade reais

Estes são os campos que o usuário efetivamente preenche. Cada um tem um `depends_on` apontando para a flag correspondente:

**Padrão de Tomada:**
```
Field Type: Select
Field Name: padrao_tomada
Label: Padrão de Tomada
Options:
  Tipo A (EUA / Japão)
  Tipo N (Brasil padrão)
  Tipo C (Europa)
  Bivolt automático
depends_on: eval:doc._tem_padrao_tomada == 1
```

**Tipo de Conector:**
```
Field Type: Select
Field Name: tipo_conector
Label: Tipo de Conector
Options:
  USB-C
  USB-A
  Micro-USB
  Lightning
  P2 (3.5mm)
  Thunderbolt 3
  Thunderbolt 4
  USB 3.0 Tipo B (HD)
  MagSafe
  Proprietário
  SD
  microSD
  CF
  CFexpress
depends_on: eval:doc._tem_tipo_conector == 1
```

**Wattagem:**
```
Field Type: Data
Field Name: wattagem
Label: Wattagem (W)
depends_on: eval:doc._tem_wattagem == 1
```

> 💡 **Por que `Data` e não `Int` para wattagem?** Porque valores como "65W", "30W GaN", "5V/2A" são comuns no mundo real e um campo numérico puro rejeita texto. Use `Data` para flexibilidade; se precisar de cálculos, considere `Float`.

**Capacidade:**
```
Field Type: Data
Field Name: capacidade
Label: Capacidade
Description: Ex: 128GB, 1TB, 20000mAh
depends_on: eval:doc._tem_capacidade == 1
```

**Classe de Velocidade:**
```
Field Type: Select
Field Name: classe_velocidade
Label: Classe de Velocidade
Options:
  Classe 4
  Classe 6
  Classe 10
  UHS-I (U1)
  UHS-I (U3)
  UHS-II
  UHS-III
  V30
  V60
  V90
depends_on: eval:doc._tem_classe_velocidade == 1
```

**Conectividade:**
```
Field Type: Select
Field Name: conectividade
Label: Conectividade
Options:
  Com fio
  Bluetooth
  2.4GHz (dongle)
  Bluetooth + 2.4GHz
depends_on: eval:doc._tem_conectividade_sem_fio == 1
```

**Layout:**
```
Field Type: Select
Field Name: layout_teclado
Label: Layout
Options:
  ABNT2 (Português BR)
  US Internacional
  UK
  Outro
depends_on: eval:doc._tem_layout == 1
```

#### Passo 5 — Adicionar campos sempre visíveis

Estes campos aparecem para qualquer tipo de acessório:

**Cor:**
```
Field Type: Data
Field Name: cor
Label: Cor
In List View: ✅
```

**Detalhes:**
```
Field Type: Small Text
Field Name: detalhes
Label: Detalhes / Observações
Description: Informações específicas não cobertas pelos campos acima
```

#### Passo 6 — Ordenar os campos e salvar

A ordem recomendada dos campos no DocType (que reflete a ordem de exibição no formulário):

```
1. tipo_acessorio         (Link — visível)
2. cor                    (Data — visível)
3. padrao_tomada          (Select — condicional)
4. tipo_conector          (Select — condicional)
5. wattagem               (Data — condicional)
6. capacidade             (Data — condicional)
7. classe_velocidade      (Select — condicional)
8. conectividade          (Select — condicional)
9. layout_teclado         (Select — condicional)
10. detalhes              (Small Text — visível)
--- campos ocultos (ordem não importa para UX) ---
11. _tem_padrao_tomada    (Check — hidden)
12. _tem_tipo_conector    (Check — hidden)
13. _tem_wattagem         (Check — hidden)
14. _tem_capacidade       (Check — hidden)
15. _tem_classe_velocidade (Check — hidden)
16. _tem_conectividade_sem_fio (Check — hidden)
17. _tem_layout           (Check — hidden)
```

Salve o DocType.

---

## 4. Adicionar o campo `Table` na Ordem de Serviço

### O que é / O que vamos fazer

Com o DocType filho criado, precisamos adicioná-lo à Ordem de Serviço como um campo do tipo `Table`. Este campo é o ponto de conexão: ele instrui o Frappe a renderizar a child table no formulário pai.

### Por que dessa forma?

O campo `Table` no Frappe funciona como uma composição — a Ordem de Serviço **contém** `Acessório Cliente`, não apenas referencia. Todos os registros filhos são carregados junto com o documento pai numa única requisição, e salvos em transação única. Isso é equivalente a um relacionamento de composição forte (cascade all) no JPA/Hibernate, ou a um documento embarcado no MongoDB.

### Passo a Passo

#### Passo 1 — Abrir o DocType da Ordem de Serviço

```
Menu lateral → Ogun → DocType List → Ordem de Serviço → Edit
```

#### Passo 2 — Localizar a seção de checklist

Na aba **Fields**, localize a seção "Checklist do Aparelho" (ou crie uma se não existir):

Para criar a seção:
```
Field Type: Section Break
Label: Checklist do Aparelho
```

#### Passo 3 — Adicionar o campo Table

Logo abaixo da seção, adicione:

```
Field Type: Table
Field Name: acessorios
Label: Acessórios Entregues
Options: Acessório Cliente
```

O campo `Options` de um campo `Table` recebe o **nome do DocType filho**. Exatamente `Acessório Cliente`.

#### Passo 4 — Salvar a Ordem de Serviço

Salve o DocType. O Frappe agora vai renderizar a tabela de acessórios no formulário.

---

## 5. Escrever o Client Script para reatividade em tempo real

### O que é / O que vamos fazer

Aqui está o ponto mais importante do guia do ponto de vista técnico: resolver a limitação do `fetch_from`.

Por padrão, `fetch_from` popula os campos de flag apenas quando o documento é **salvo**. Isso significa que se o usuário selecionar "Carregador" na linha da tabela, os campos `padrao_tomada`, `tipo_conector` e `wattagem` não vão aparecer imediatamente — só após salvar. Essa UX é inaceitável para um formulário de atendimento.

A solução é um **Client Script**: código JavaScript que o Frappe executa no contexto do formulário, no navegador do usuário. Vamos capturar o evento de mudança do campo `tipo_acessorio`, buscar as flags via `frappe.db.get_value`, e escrever os valores diretamente na linha da child table, disparando a reatividade do `depends_on`.

### Por que dessa forma?

Client Scripts no Frappe são o equivalente aos **event listeners e hooks de formulário** que você conhece do React (onChange, useEffect) — exceto que aqui o "estado" é o documento Frappe e a "re-renderização" é feita pelo framework automaticamente ao mudar valores com `frappe.model.set_value`.

`frappe.db.get_value` faz uma requisição REST ao backend Frappe (uma chamada para `/api/resource/Tipo Acessório/{name}`) e retorna os valores solicitados. É equivalente a um `fetch('/api/tipo-acessorio/:id')` que você faria no frontend React para buscar dados de uma entidade.

O padrão que vamos usar — capturar evento no filho, buscar dado no mestre, escrever de volta no filho, forçar refresh — é um padrão recorrente em Client Scripts do Frappe. Vale memorizar.

### Passo a Passo

#### Passo 1 — Criar o Client Script

```
Menu lateral → Configurações → Client Script → New
```

Ou acesse: `/app/client-script/new-client-script`

#### Passo 2 — Configurar o Client Script

| Campo | Valor |
|---|---|
| **Enabled** | ✅ |
| **Document Type** | `Ordem de Serviço` |
| **Script Type** | `Form` |

> 💡 **Nota:** o Client Script é definido no DocType **pai** (`Ordem de Serviço`), não no filho. No Frappe, Client Scripts de child tables são sempre escritos no contexto do pai — o filho não tem formulário próprio.

#### Passo 3 — Escrever o script

```javascript
// Este script roda no contexto do formulário de Ordem de Serviço.
// Capturamos eventos que acontecem dentro da child table "acessorios",
// especificamente no campo "tipo_acessorio" de cada linha.

frappe.ui.form.on('Acessório Cliente', {

  // Este evento dispara quando o usuário muda o campo "tipo_acessorio"
  // em qualquer linha da tabela "acessorios".
  //
  // Parâmetros fornecidos pelo Frappe:
  //   frm  → o objeto do formulário pai (Ordem de Serviço)
  //   cdt  → Child DocType name = "Acessório Cliente"
  //   cdn  → Child DocType Name = o "name" único da linha atual (ex: "row-abc123")
  tipo_acessorio: function(frm, cdt, cdn) {

    // Recuperamos o objeto da linha atual usando os identificadores cdt e cdn.
    // locals é um cache global do Frappe que armazena todos os objetos de
    // documento carregados na sessão atual — incluindo as linhas de child tables.
    let row = locals[cdt][cdn];

    // Se o campo foi limpo (usuário apagou a seleção), zeramos todas as flags
    // para garantir que nenhum campo condicional fique visível erroneamente.
    if (!row.tipo_acessorio) {
      _reset_flags(frm, cdt, cdn);
      return;
    }

    // frappe.db.get_value faz uma requisição REST ao backend para buscar
    // campos específicos de um registro de um DocType.
    //
    // Assinatura: frappe.db.get_value(doctype, name, fieldnames, callback)
    //
    // Aqui pedimos todos os campos de flag do tipo de acessório selecionado.
    frappe.db.get_value(
      'Tipo Acessório',           // DocType a consultar
      row.tipo_acessorio,         // name do registro (ex: "Carregador")
      [                           // lista de campos a retornar
        'tem_padrao_tomada',
        'tem_tipo_conector',
        'tem_wattagem',
        'tem_capacidade',
        'tem_classe_velocidade',
        'tem_conectividade_sem_fio',
        'tem_layout'
      ],
      function(values) {
        // "values" é um objeto com os campos solicitados e seus valores.
        // Ex: { tem_padrao_tomada: 1, tem_tipo_conector: 1, tem_wattagem: 1, ... }

        if (!values) {
          // Segurança: se o tipo não foi encontrado (registro deletado, etc.),
          // resetamos as flags para evitar estado inconsistente.
          _reset_flags(frm, cdt, cdn);
          return;
        }

        // frappe.model.set_value escreve um valor no cache local da linha
        // e notifica o Frappe para reavaliar o formulário (incluindo depends_on).
        //
        // Precisamos usar o prefixo _ nos nomes dos campos de destino, porque
        // é assim que nomeamos as flags em Acessório Cliente.
        frappe.model.set_value(cdt, cdn, '_tem_padrao_tomada',       values.tem_padrao_tomada || 0);
        frappe.model.set_value(cdt, cdn, '_tem_tipo_conector',        values.tem_tipo_conector || 0);
        frappe.model.set_value(cdt, cdn, '_tem_wattagem',             values.tem_wattagem || 0);
        frappe.model.set_value(cdt, cdn, '_tem_capacidade',           values.tem_capacidade || 0);
        frappe.model.set_value(cdt, cdn, '_tem_classe_velocidade',    values.tem_classe_velocidade || 0);
        frappe.model.set_value(cdt, cdn, '_tem_conectividade_sem_fio',values.tem_conectividade_sem_fio || 0);
        frappe.model.set_value(cdt, cdn, '_tem_layout',               values.tem_layout || 0);

        // Forçamos o refresh do campo "acessorios" no formulário pai.
        // Isso instrui o Frappe a re-renderizar a child table, o que faz
        // os depends_on serem reavaliados com os novos valores das flags.
        frm.refresh_field('acessorios');
      }
    );
  }
});

// Função auxiliar: zera todas as flags de uma linha.
// Chamada quando o tipo é limpo ou não encontrado.
function _reset_flags(frm, cdt, cdn) {
  let flag_fields = [
    '_tem_padrao_tomada',
    '_tem_tipo_conector',
    '_tem_wattagem',
    '_tem_capacidade',
    '_tem_classe_velocidade',
    '_tem_conectividade_sem_fio',
    '_tem_layout'
  ];

  flag_fields.forEach(function(field) {
    frappe.model.set_value(cdt, cdn, field, 0);
  });

  frm.refresh_field('acessorios');
}
```

#### Passo 4 — Salvar o Client Script

Clique em **Save**. O Frappe vai minificar e servir este script automaticamente para todos os usuários que abrirem um formulário de Ordem de Serviço.

> 💡 **Sobre a função auxiliar `_reset_flags`:** no Frappe, não existe módulo de importação no Client Script — o arquivo é avaliado inteiro no escopo global da página. Funções definidas com `function` no escopo raiz ficam disponíveis globalmente dentro do script. Não há problema de colisão desde que você nomeie com um prefixo único (`_reset_flags` é suficientemente específico).

---

## 6. Testar o fluxo completo

### O que é / O que vamos fazer

Teste manual do fluxo ponta a ponta para validar que todos os componentes estão integrados corretamente.

### Passo a Passo

#### Passo 1 — Abrir ou criar uma Ordem de Serviço

Navegue até o formulário de Ordem de Serviço. Localize a seção "Checklist do Aparelho" com a tabela "Acessórios Entregues".

#### Passo 2 — Adicionar uma linha à tabela

Clique em **Add Row**. Uma nova linha aparece na tabela.

#### Passo 3 — Selecionar "Carregador" como tipo

No campo **Tipo de Acessório** da nova linha, selecione "Carregador".

**Resultado esperado imediato (sem salvar):** os campos `Padrão de Tomada`, `Tipo de Conector` e `Wattagem` devem aparecer na linha. Os campos `Capacidade`, `Classe de Velocidade`, `Conectividade` e `Layout` devem permanecer ocultos.

Se isso não acontecer imediatamente, verifique:
- O Client Script está habilitado e salvo corretamente
- O nome do campo na child table (`acessorios`) corresponde exatamente ao `fieldname` no DocType pai
- O console do navegador (F12) não mostra erros JavaScript

#### Passo 4 — Trocar para "Cartão de Memória"

Mude o Tipo de Acessório para "Cartão de Memória".

**Resultado esperado:** `Padrão de Tomada` e `Wattagem` devem desaparecer. `Capacidade`, `Classe de Velocidade` e `Tipo de Conector` devem aparecer.

#### Passo 5 — Preencher os campos e salvar

Preencha os campos visíveis e salve o documento. Reabra o documento e verifique se os valores foram persistidos corretamente e se os campos condicionais voltam a aparecer com os valores corretos.

#### Passo 6 — Verificar no banco (opcional mas recomendado)

Conecte ao banco MariaDB para verificar que as flags estão sendo persistidas corretamente:

```bash
# No servidor onde o bench está rodando
bench --site neogen-erp-v0.1.local mariadb

# No prompt do MariaDB
SELECT name, parent, tipo_acessorio, 
       _tem_padrao_tomada, _tem_tipo_conector, _tem_wattagem,
       padrao_tomada, tipo_conector, wattagem, cor, detalhes
FROM `tabAcessório Cliente`
WHERE parent IS NOT NULL
LIMIT 10;
```

Você deve ver as flags como `0` ou `1` e os campos de propriedade preenchidos onde aplicável.

---

## 7. Exportar os fixtures para versionamento

### O que é / O que vamos fazer

Os registros de `Tipo Acessório` que você criou são **fixtures** — dados de configuração que fazem parte do sistema e devem ser versionados junto com o código do app Ogun no Git. Se você reinstalar o sistema ou subir para produção, esses registros precisam estar lá automaticamente.

O Frappe tem um mecanismo nativo para isso: o diretório `fixtures` dentro do app, e o comando `bench export-fixtures`.

### Por que dessa forma?

A distinção entre dados de configuração (fixtures) e dados de negócio (transações) é um princípio fundamental de qualidade em sistemas ERP. Fixtures são reproduzíveis, determinísticos e devem viver no repositório. Dados de negócio vivem no banco de produção. Misturar os dois gera ambientes impossíveis de replicar.

Isso é análogo a separar seeds de migrations no mundo Rails/Django, ou a separar dados de ambiente de dados de usuário em qualquer sistema web.

### Passo a Passo

#### Passo 1 — Declarar os fixtures no `hooks.py` do app Ogun

Abra o arquivo de hooks do seu app:

```bash
# No terminal, no diretório do bench
nano apps/ogun/ogun/hooks.py
```

Adicione a declaração de fixtures:

```python
# hooks.py

# Fixtures: dados de configuração que devem ser versionados com o app.
# O Frappe exporta e importa esses registros automaticamente via
# `bench export-fixtures` e `bench --site X install-app ogun`.
fixtures = [
    {
        # Exporta todos os registros de Tipo Acessório
        "doctype": "Tipo Acessório",
        # Sem filtros = exporta todos os registros.
        # Se quiser filtrar: "filters": [["module", "=", "Ogun"]]
    }
]
```

#### Passo 2 — Exportar os fixtures

```bash
bench --site neogen-erp-v0.1.local export-fixtures
```

O Frappe vai criar (ou atualizar) o arquivo:

```
apps/ogun/ogun/fixtures/tipo_acessorio.json
```

Este arquivo contém todos os registros de `Tipo Acessório` em formato JSON.

#### Passo 3 — Verificar o conteúdo exportado

```bash
cat apps/ogun/ogun/fixtures/tipo_acessorio.json
```

Você deve ver algo como:

```json
[
  {
    "doctype": "Tipo Acessório",
    "name": "Carregador",
    "categoria": "Alimentação",
    "tem_padrao_tomada": 1,
    "tem_tipo_conector": 1,
    "tem_wattagem": 1,
    "tem_capacidade": 0,
    ...
  },
  {
    "doctype": "Tipo Acessório",
    "name": "Cabo",
    ...
  }
]
```

#### Passo 4 — Commitar no Git

```bash
cd apps/ogun
git add ogun/fixtures/tipo_acessorio.json
git add ogun/hooks.py
git commit -m "feat: adiciona fixtures de Tipo Acessório com flags de propriedades"
```

#### Passo 5 — Validar a importação (opcional)

Para garantir que os fixtures funcionam na reinstalação, você pode simular importando manualmente:

```bash
bench --site neogen-erp-v0.1.local import-fixtures
```

Este comando é executado automaticamente durante `bench --site X install-app ogun` em novos ambientes.

---

## Armadilhas Comuns

### `depends_on` não reage após mudar o tipo

**Causa:** o Client Script não está sendo carregado. Verifique se está habilitado (`Enabled: ✅`) e se o `Document Type` está correto (`Ordem de Serviço`, não `Acessório Cliente`).

**Debug:** abra o console do navegador (F12) e execute `frappe.ui.form.on` — se o evento não estiver registrado, o script não carregou.

### Campos de flag ficam zerados após salvar

**Causa:** o `fetch_from` está sobrescrevendo os valores que o Client Script definiu, porque o Frappe executa o `fetch_from` no save e busca os valores do banco — que estão corretos. Isso geralmente não é um problema real, mas se ocorrer, verifique se `fetch_from` está configurado no campo correto.

### `frappe.db.get_value` retorna `null`

**Causa:** o name do tipo no campo Link contém espaços extras ou capitalização diferente. O Frappe é case-sensitive nos nomes. Verifique com um `console.log(row.tipo_acessorio)` antes da chamada.

### Child table não aparece no formulário pai

**Causa:** o `fieldname` do campo `Table` na Ordem de Serviço não bate com o nome usado no Client Script. Se o campo se chama `acessorios_cliente` no DocType, use `frm.refresh_field('acessorios_cliente')`.

---

## Referências

- [Frappe DocType Documentation](https://frappeframework.com/docs/user/en/understanding-doctypes)
- [Frappe Child Tables](https://frappeframework.com/docs/user/en/table-fields)
- [fetch_from field property](https://frappeframework.com/docs/user/en/fetch-from)
- [Client Scripts in Frappe](https://frappeframework.com/docs/user/en/client-scripts)
- [frappe.db.get_value API](https://frappeframework.com/docs/user/en/api/frappe.db)
- [Fixtures and Data Migration](https://frappeframework.com/docs/user/en/fixtures)
- [hooks.py reference](https://frappeframework.com/docs/user/en/python-api/hooks)
