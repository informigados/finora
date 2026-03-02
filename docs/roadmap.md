# FINORA SaaS - Roadmap de Evolução e Produto

Este roadmap traça a evolução do **FINORA SaaS** a partir do seu MVP, adicionando módulos estruturais profundos e inteligência de dados para transformar o sistema em um produto de altíssimo valor de mercado.

---

## 🟢 NÍVEL 1: Fundações Financeiras Avançadas
*Transformando o sistema de "caixa único" em uma plataforma completa de gestão de patrimônio.*

- [ ] **Sistema Multi-Contas (Carteiras):**
  - Fim do "caixa único". Lançamentos deverão pertencer a origens específicas.
  - Módulos para: Conta Corrente, Poupança, Carteira Física (Dinheiro de bolso), Contas PJ e Carteiras de Investimento.
- [ ] **Módulo Completo de Cartão de Crédito:**
  - Gestão de Fatura Mensal (lançamentos caem na fatura, e o pagamento da fatura abate a conta corrente).
  - Lançamento de Parcelamentos (geração automática das X parcelas futuras).
  - Visualização de Limite Disponível.
  - Controle preditivo do melhor dia para compra e fechamento.
- [ ] **Customização Total de Categorias:**
  - Interface visual (CRUD) para que o usuário crie, edite e exclua suas próprias categorias de gasto/ganho.
  - Seleção de cores Hex/Tailwind e ícones (Lucide Icons) personalizados.
- [ ] **Metas Financeiras Inteligentes:**
  - Simulador de alcance: "Se você guardar R$ X por mês, alcançará a meta em Y meses."

---

## 🟡 NÍVEL 2: Diferencial Competitivo e Engajamento
*Implementação de features que geram retenção ("vício" positivo) e entregam valor analítico sem que o usuário precise fazer cálculos.*

- [ ] **Dashboard com Insights Ativos (Inteligência):**
  - Resumos textuais gerados dinamicamente no topo do painel:
    - *"Você gastou 32% a mais em Alimentação este mês em relação à sua média."*
    - *"Seu padrão de gastos está estável. Você pode economizar R$ X reduzindo a categoria Y."*
  - Exibição de Saldo Médio Móvel (ex: últimos 3 meses).
- [ ] **Gráfico de Evolução Patrimonial (Net Worth):**
  - Gráfico de linha temporal unindo todas as contas, projetando o crescimento do saldo financeiro total ao longo de meses e anos.
- [ ] **Lançamentos Recorrentes Complexos:**
  - Interface granular para gerenciar recorrências.
  - Suporte a frequências diárias, semanais, quinzenais, e personalizadas.
- [ ] **Sistema de Alertas e Notificações In-App:**
  - Avisos (via painel e e-mail) sobre despesas próximas do vencimento, faturas fechando, e metas atrasadas.

---

## 🔵 NÍVEL 3: Visão Enterprise (Escala Premium SaaS)
*Funcionalidades profundas para usuários exigentes (SaaS pago, plano Pro/Premium).*

- [ ] **Relatórios Inteligentes e Exportação Avançada:**
  - Geração de "DRE Pessoal" detalhado anualmente.
  - Relatórios isolados filtrados especificamente por Conta, Categoria ou Período, com layouts de alta fidelidade visual (infográficos).
- [ ] **Comparativo Estratégico de Períodos:**
  - Telas lado-a-lado ou sobreposição em gráficos: Ex: *Fevereiro 2026 vs Fevereiro 2025* ou *Último Trimestre vs Trimestre Anterior*.
- [ ] **Sistema de Tags Customizadas (Multi-dimensional):**
  - Classificação paralela às categorias. Adição de tags `#ViagemOrlando`, `#DespesaEmpresa`, permitindo a geração de relatórios cruzados instantâneos.
- [ ] **Automação de Nuvem e Integrações:**
  - Rotinas de Backup automático dos dados isolados do usuário na nuvem do sistema, com envio periódico do snapshot de segurança.
  - (Futuro) Importação nativa de extratos OFX para conciliação bancária rápida.

---

## 🧭 Estrutura Final de Navegação (Visão de Produto)
Quando o roadmap estiver concluído, o FINORA SaaS possuirá a seguinte espinha dorsal na sua barra lateral/menus:

1. **Painel Inteligente** (Saldos Globais, Gráfico Evolutivo e Insights Textuais)
2. **Contas & Carteiras**
3. **Cartões de Crédito**
4. **Lançamentos** (Visões em Tabela e Calendário)
5. **Metas Financeiras**
6. **Relatórios & Analytics** (Comparações e DRE)
7. **Configurações** (Categorias, Tags, Perfil, Preferências de Alertas)
