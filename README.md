# Seiden FLOW 0.24.2

## 0.24.2 — EEA/TCA Profile Ownership Architecture

Esta release corrige a responsabilidade arquitetural dos perfis ambientais. O Seiden Vision deixa de ser autoridade das faixas analíticas; o Flow passa a possuir os catálogos EEA e TCA em arquivos persistentes independentes.

- `/config/config_eea.json`: `human_indoor`, `human_outdoor` e futuros perfis de experiência ambiental humana/contextual.
- `/config/config_tca.json`: `refrigerator`, `freezer`, `wine_cellar`, `beer_cooler` e futuros perfis de conformidade térmica.
- Se o catálogo legado do Vision existir na primeira execução, suas faixas são preservadas e separadas automaticamente, sem apagar o original.
- O EEA filtra também o histórico pela ownership atual: equipamentos térmicos não aparecem mais no portal EEA.
- `human_outdoor` permanece visível como contexto externo, mas não gera falso estado operacional nos KPIs de conforto interno.



## 0.24.1 — HAOS Stability Hotfix

Hotfix de estabilidade após validação da 0.24.0 em ambiente HAOS real.

- ERA passa a respeitar `ita_fleet_enabled` antes de sincronizar o Fleet Receiver.
- Indisponibilidade do Fleet Receiver opcional deixa de gerar traceback repetitivo; o estado é registrado como warning operacional com supressão de repetição por 5 minutos.
- O cliente Fleet deixa erros transitórios de conexão/timeout em nível debug, evitando duplicidade de logs.
- A migração legada de domínio recebe marcador persistente e passa a executar uma única vez por banco; reinícios posteriores não percorrem novamente todo o histórico.
- `DATABASE_SCHEMA_VERSION` permanece 23; nenhuma alteração destrutiva de banco.

## 0.24.0 — HAOS Functional Alignment with Flow Linux

Esta release traz ao add-on HAOS as melhorias funcionais e de UX amadurecidas no Flow Linux, preservando a arquitetura nativa do Home Assistant e o banco SQLite.

### Principais evoluções

- Home comercial Seiden One em `/`; dashboard operacional preservado em `/operation`.
- EEA oficial em `/eea`, com aliases legados para compatibilidade.
- EEA passa a interpretar envelopes ambientais Bridge 2.0 do perfil `human_indoor`.
- TCA passa a tratar `tca_bindings` como autoridade para o ativo térmico lógico e evita materializar eventos ambientais não vinculados.
- Reconciliação histórica idempotente do TCA após criação/edição de bindings.
- Nova opção `tca_enabled` no add-on.
- ITA recebe exclusão permanente de ativo local e UX alinhada às melhorias recentes do Linux.
- Branding, navegação, tema e idioma alinhados entre os portais.
- Banco permanece SQLite; nenhuma camada PostgreSQL/Linux foi incorporada.


## ERA 0.1.1 + TCA 0.6.1 — TCA Response Integration

A ERA passa a consumir automaticamente o estado analítico do TCA, validando
a arquitetura transversal da Seiden One.

### Eventos TCA publicados para a ERA

- `temperature.attention` — temperatura fora da faixa ideal; warning.
- `temperature.critical` — temperatura fora dos limites operacionais; critical.
- `door.open_too_long` — porta aberta acima do limite configurável; warning.
- `thermal_recovery.abnormal` — recuperação térmica não concluída; warning.

### Comportamento

- O TCA continua responsável por interpretar o contexto térmico.
- A ERA continua responsável por correlação, deduplicação, política, notificação
  e recuperação.
- Telegram recebe contexto TCA útil, incluindo temperatura atual e faixa ideal.
- O adapter TCA é executado server-side pela ERA; não depende da tela TCA estar aberta.
- Nenhuma lógica Telegram foi duplicada dentro do TCA.
- Banco principal, Pulse Protocol e Receiver permanecem inalterados.

### Defaults de laboratório

- TCA → ERA: habilitado.
- Janela analítica: 24 h.
- Porta aberta excessiva: 5 min.
- Warning ERA: após 10 min.
- Critical ERA: imediato.
