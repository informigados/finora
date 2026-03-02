# FINORA SaaS - Minimum Viable Product (MVP)

Este documento define o Produto Mínimo Viável (MVP) para a construção do **FINORA SaaS**, um sistema financeiro moderno, web-based e voltado para comercialização (multi-tenant). O projeto será construído **do zero**, focado na melhor experiência e escalabilidade.

## 🧰 Stack Tecnológica Principal
- **Back-end:** Laravel (PHP 8.x)
- **Front-end / Templates:** Motor Blade com HTML5
- **Estilização e UI/UX:** Tailwind CSS (Visual Glassmorphism, Premium SaaS)
- **Interatividade:** Alpine.js (para reatividade leve, modais, dropdowns)
- **Banco de Dados:** MySQL / MariaDB

---

## 🚀 Escopo do MVP (Versão 1.0)
Estas são as funcionalidades obrigatórias para o lançamento inicial do produto no mercado.

### 1. Sistema Base e Multi-Tenant
- **Autenticação Pessoal:** Sistema de Registro, Login, Recuperação de Senha (utilizando Laravel Breeze/Fortify).
- **Isolamento de Dados (Tenant Básico):** Estrutura de banco de dados onde cada usuário acessa única e exclusivamente seus próprios dados financeiros.
- **Múltiplos Idiomas (i18n):** Suporte arquitetural para Português, Inglês e Espanhol.
- **Tema Dinâmico:** Suporte a Light Mode e Dark Mode via Tailwind.

### 2. Gestão Financeira Essencial
- **Painel de Controle (Dashboard):** Visão geral do mês com Saldo Geral, Total Pago, Total Pendente e Total Atrasado. Gráficos simples do fluxo mensal (Chart.js).
- **Gestão de Lançamentos:**
  - Cadastro de Receitas e Despesas.
  - Campos: Descrição, Valor, Categoria, Tipo, Status (Pago/Pendente), Data de Vencimento, Data de Pagamento e Observações.
- **Visualização Temporal:** Filtros e telas para o usuário navegar pelos Lançamentos separados por Mês e por Ano.

### 3. Engajamento e Planejamento
- **Metas Financeiras:** Criação de objetivos financeiros com valor alvo, valor atual, prazo e barras de progresso visuais.
- **Orçamentos (Budgets):** Definição de limite de gastos mensal por categoria, com cálculo de porcentagem gasta.
- **Recorrência Simples:** Motor básico acionado por CRON (Laravel Scheduler) para gerar automaticamente lançamentos fixos (mensais ou anuais).

### 4. Utilidades e Exportação
- **Exportação de Dados:** Geração de relatórios básicos do mês atual em PDF (via DomPDF) e exportação de tabelas para CSV/TXT.
- **Backup Manual:** Botão para o usuário solicitar e baixar um arquivo `.zip` ou equivalente com seus dados brutos de segurança.

---

📋 **Objetivo do MVP:** Entregar uma ferramenta robusta, com design extremamente comercial e premium, resolvendo o problema central de organização financeira do usuário para então escalar com as features de diferencial competitivo (detalhadas no Roadmap).
