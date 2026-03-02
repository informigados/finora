# 1️⃣ VISÃO DO SISTEMA

Nome do projeto

FINORA
(curto, forte, soa como “finance” + “ora”, agora)

FINORA – Financial Organizer & Analyzer

O que ele é

Um organizador financeiro pessoal, executado localmente em Python, mas acessado pelo navegador, com:

Interface moderna (dashboard)

Dados salvos em banco interno

Organização mensal e anual

Exportação profissional

Zero dor de cabeça

2️⃣ FUNCIONALIDADES NATURAIS (ALÉM DO EXCEL)
📥 Cadastro de despesas e receitas

Campos:

- Descrição
- Valor
- Categoria
- Tipo (Despesa / Receita)
- Status (Pago / Pendente / Atrasado)
- Data de vencimento
- Data de pagamento
- Observações

Tudo preenchido direto no navegador, com suporte a **Lançamentos Recorrentes** (Mensais, Semanais, Diários, Anuais).

📆 Organização por período

- Visualização por mês
- Visualização por ano
- Histórico automático (sem duplicar planilha)

📊 Resumos automáticos
Por mês e por ano:

- Total pago
- Total pendente
- Total atrasado
- Total geral
- Pendentes + atrasados
- Gráfico de Despesas por Categoria

📤 Exportações & Importações

- Download com 1 clique: CSV, TXT, PDF Profissional
- **Importação Dinâmica**: Suporte a envio de dados via planilhas CSV/Excel para rápido preenchimento.

🧠 Inteligência básica

- Destaque automático de atrasados e alertas visuais.
- Cálculo automático estruturado no banco.

3️⃣ RECURSOS ENTERPRISE E SEGURANÇA (NOVIDADES)

- **Autenticação Pessoal**: Login e senha protegidos, com chave de recuperação via token UUID.
- **Múltiplos Idiomas (i18n)**: Suporte nativo ao Português (Brasil), Inglês e Espanhol.
- **Controle Orçamentário (Budgets)**: Criação de tetos de gastos mensais por categoria.
- **Metas Financeiras (Goals)**: Sistema visual de progresso para economia alvejada.
- **Segurança de Dados**: Validação MIME real para imagens de perfil contra uploads maliciosos.
- **Start Avançado**: Executáveis CLI robustos com elevação real de Administrador, detecção inteligente de porta HTTP e verificação assíncrona de dependências PIP.
- **UI/UX Premium**: Design escalável construído sob o conceito de *Glassmorphism* moderno com fontes tipográficas do Google (Inter, Outfit).

---

# 4️⃣ ROADMAP DE EVOLUÇÃO E PRODUTO (RECOMENDAÇÕES)

Estas recomendações estruturais visam evoluir o FINORA de um "controle organizado" focado em caixa único para um verdadeiro produto de nível SaaS, robusto o suficiente para concorrer visualmente e tecnicamente com os melhores organizadores do mercado.

## 🟢 NÍVEL 1 — O que está faltando e é quase obrigatório

### 1️⃣ Contas / Carteiras (Sistema Multi-Contas)
Atualmente o sistema funciona em um "caixa único". Cada lançamento precisa pertencer a uma conta específica.

- [ ] Módulo de Contas Correntes
- [ ] Poupança
- [ ] Cartões de Crédito (vinculados ou não)
- [ ] Carteira Física (dinheiro vivo)
- [ ] Contas PJ
- [ ] Investimentos

### 2️⃣ Cartão de Crédito (Módulo Separado)
Cartões operam de forma diferente das contas tradicionais.

- [ ] Fatura Mensal (visualização e fechamento)
- [ ] Lançamento de Parcelamentos Automáticos de compras no crédito
- [ ] Visualização de Limite Disponível
- [ ] Controle de fechamento e melhor dia para compra

### 3️⃣ Metas Financeiras mais Inteligentes
Engajamento via metas gamificadas.

- [x] Módulo base de Metas criado
- [x] Meta com prazo
- [x] Barra de progresso visual
- [ ] Simulação automática ("Se guardar X por mês, alcança em Y")

### 4️⃣ Categorias Editáveis pelo Usuário
O usuário deve possuir controle sobre onde seu dinheiro vai, fugindo do hardcode.

- [ ] Interface CRUD completa para categorias
- [ ] Escolha de Cores (tags visuais)
- [ ] Escolha de Ícones

## 🟡 NÍVEL 2 — Diferencial Real

### 5️⃣ Dashboard com Insights Automáticos
O painel precisa "conversar" com a pessoa e mostrar inteligência sobre os hábitos.

- [ ] Resumo do tipo: "Você gastou 32% a mais em Alimentação este mês."
- [ ] Resumo do tipo: "Seu maior gasto foi X."
- [ ] Demonstração de Saldo Médio: "Seu saldo médio dos últimos 3 meses é Y."

### 6️⃣ Gráfico de Patrimônio Acumulado
Poderoso para retenção.

- [ ] Gráfico em Linha mostrando a evolução do saldo acumulativo (Net Worth) ao longo do tempo.

### 7️⃣ Lançamentos Recorrentes Automáticos
Estrutura para contas a pagar e receber repetitivas.

- [x] Sistema base de recorrência (crons via login ou job schedules)
- [x] Lançamentos Mensais automatizados
- [x] Lançamentos Anuais automatizados
- [ ] Opção para quinzenais ou diários em interface granular

### 8️⃣ Sistema de Alertas
Notificações preventivas (atualmente temos estilo visual late/warning, mas não alertas diretos prévios).

- [ ] Alerta de despesa próxima ao vencimento
- [ ] Alerta de limite do cartão quase atingido
- [ ] Notificação interna de Meta Atrasada / Saldo abaixo da Meta

## 🔵 NÍVEL 3 — Produto Nível SaaS (Enterprise Múltiplo)

### 9️⃣ Exportação Avançada (Relatórios Inteligentes)

- [x] Download em CSV / TXT em tabelas normais
- [x] Download em PDF da visão base
- [ ] Relatório anual detalhado em infográfico gerado 
- [ ] Relatório isolado por categoria
- [ ] Relatório isolado por conta

### 🔟 Comparação de Períodos

- [ ] Comparação mês vs mês do ano anterior (ex: Fev 2026 vs Fev 2025)
- [ ] Comparativo dos últimos 3 meses para identificar inflação de custo fixo

### 11️⃣ Sistema de Tags Customizadas

- [ ] Associações orgânicas a lançamentos: Ex: "#ViagemOrlando", "#Empresa", "#Curso"
- [ ] Relatórios cruzados de Categorias x Tags

### 12️⃣ Backup e Retenção

- [x] Exportação de dados manuais
- [x] Snapshot manual local compactado (.zip sqlite)
- [ ] Backup automático na nuvem (1 clique)

---

## 🧠 VISÃO ESTRATÉGICA FINAL (SaaS)

Para transformar definitivamente o FINORA num SaaS viável e vendido, a estrutura de navegação e operação precisará se basear em:

1. **Painel** (Dashboard)
2. **Contas** (Bancos e Carteiras)
3. **Cartões** (Faturas e Limites)
4. **Lançamentos** (Receitas, Despesas, Transferências entre Contas)
5. **Metas** (Projetos Financeiros)
6. **Relatórios** (Análise Avancada e Comparativos Diários/Anuais)
7. **Configurações** (Perfil, Tags, Categorias)

**No Painel Principal**, o resumo deve dominar o topo:
> *"Seu padrão de gastos está estável."*
> *"Você pode economizar R\$ X reduzindo Y neste mês."*
