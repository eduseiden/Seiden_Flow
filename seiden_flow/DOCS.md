# Seiden FLOW 0.22.1.9 — Documentação técnica

## ITA 0.3.1.8 — Operational Overview Refinement

A home representa o estado atual da infraestrutura. O período fica contextual no detalhe local/Bridge.

Ordenação:
- Monitorados/Todos e Normais: alfabética;
- Atenção/Críticos: severidade e ocorrência mais recente;
- Sem telemetria: maior tempo sem atualização primeiro.

Para `linux_host`, os cards principais são CPU, Memória, Disco e Uptime quando presentes no resumo Fleet.

---

# Seiden FLOW 0.16.1.1 — Documentação técnica

## LCA 0.4.0.2 — Bridge State Transition Support

Eventos compactos `state_transition` emitidos pelo MQTT State Driver do Bridge são convertidos em evidência de estado do LCA. Em um canal `direct`, a transição atualiza o estado canônico e as sessões do circuito. Em canais `parallel`, a origem continua sendo determinada pelo contrato `lighting_interaction` publicado em `seiden/lca/interactions`, evitando dupla contagem.


## LCA 0.4.0.2 — Circuit Usage UX Refinement

O LCA 0.4.0.2 preserva as sessões canônicas introduzidas no LCA 0.4.0 e refina a apresentação de uso. O LCA 0.4.0 adiciona sessões canônicas no nível do circuito (`lca_circuit_sessions`). Uma sessão começa somente quando o estado canônico do circuito muda para `on` e termina quando muda para `off`. Evidências repetidas no mesmo estado não reiniciam a sessão.

O endpoint `/api/v1/lca/dashboard` passa a expor `usage_summary` e `usage_by_circuit`. As durações são recortadas ao período selecionado no dashboard; assim, uma sessão iniciada antes da janela contribui apenas com o trecho observado dentro dela.

Métricas disponíveis:

- `total_on_seconds`;
- `session_count`;
- `average_session_seconds`;
- `longest_session_seconds`;
- `utilization_pct`;
- `current_session_seconds`;
- `current_session_started_at`.

A migração `lca_circuit_usage_sessions_040` reconstrói sessões históricas a partir das interações confirmadas existentes. O `DATABASE_SCHEMA_VERSION` passa a 19.


## Refinamento de apresentação 0.4.0.2

A seção **Tempo de uso** deixa de funcionar como inventário completo e passa a priorizar análise operacional:

- por padrão, somente circuitos com uso no período são exibidos;
- o filtro **Local** permite restringir a análise a um ambiente sem alterar o período global do dashboard;
- **Mostrar sem uso** expõe circuitos sem sessões apenas quando necessário para auditoria;
- KPIs de tempo/sessões respeitam o local selecionado e consideram somente circuitos efetivamente usados;
- a lista permanece ordenada por tempo ligado decrescente;
- pluralização de `sessão/sessões` é tratada explicitamente na interface.

Os filtros são aplicados na camada de apresentação sobre `usage_by_circuit`; não alteram persistência, sessões ou estado canônico. O schema permanece em 19.

## Compatibilidade visual

A interface mantém integralmente a base visual da LCA 0.3.9.x. A nova seção “Tempo de uso” usa os mesmos tokens, superfícies, tipografia, responsividade e contraste em modo claro/escuro.

---


## LCA 0.3.9.3 — Canonical Circuit State

O estado operacional de uma carga passa a ser persistido em `lca_circuit_state`, indexado por `light_id`. Pontos diretos e paralelos continuam sendo fontes de interação e evidência, mas seus estados técnicos não são mais usados para recalcular o estado atual da carga.

Uma interação com `requested_state` confirmado atualiza o estado canônico. A migração 0.3.9.3 inicializa circuitos existentes pela interação confirmada mais recente e usa `lca_channel_state` somente como baseline de compatibilidade quando não há histórico lógico.

O dashboard usa `lca_circuit_state` tanto para `active_lights` quanto para `current_lights`, garantindo uma única fonte de verdade após refresh. Eventos fora de ordem são ignorados quando mais antigos que `last_changed_at`.

Database Schema: `18`. UX/UI da LCA 0.3.9 preservada integralmente.

## LCA 0.3.9.2 — Logical State Regression Fix

- monitored circuits use a compact state-dot model with direct/parallel breakdown reserved for advanced mode;
- amber is reserved for active lighting/state semantics, while analytic charts use blue/purple/neutral palettes;
- dark theme includes explicit contrast overrides for metadata, subtitles, controls, legends and separators;
- singular/plural labels are rendered naturally for channels and scene executions.


A identidade estrutural passa a ser `dispositivo MQTT + canal canônico`. O tópico `zigbee2mqtt/Interruptor Sala` representa o dispositivo e L1/L2/L3/... representam suas teclas. `source_entity` de eventos explícitos é evidência técnica e nunca promove uma entidade amigável a dispositivo. Interações sem identidade técnica resolvível são associadas ao ponto correto por `circuit_id` e pela transição MQTT observada na janela causal.

A migração 0.3.7 marca como ignorados os dispositivos sintéticos criados anteriormente a partir de `seiden/lca/interactions` quando eles não possuem mudanças reais de estado.

Database Schema: `17`.


## LCA 0.3.6 — circuitos lógicos e pontos de acionamento

O LCA diferencia o **circuito de iluminação** (a carga real iluminada) dos **pontos de acionamento** (retorno direto, paralelo, cena ou interface). O identificador `circuit_id` é estável e independe de nomes técnicos de dispositivos. Duplicidades seguras são consolidadas automaticamente, com auditoria em `lca_light_merge_log`.

O dashboard expõe `monitored_lights`, `active_lights`, `monitored_points`, `direct_points`, `parallel_points` e `configuration_quality`.
# Seiden FLOW 0.15.6 — Documentação técnica

## LCA 0.3.6 — Logical Circuit Consolidation

O endpoint `/api/v1/lca/dashboard` aceita `hours`, `action_page` e `action_page_size`. A paginação das ações é realizada no SQLite, evitando carregar todo o histórico no navegador.

### Períodos e paginação

- períodos suportados pelo portal: 1 h, 6 h, 24 h, 7 dias e 30 dias;
- `action_page` começa em 1;
- `action_page_size` aceita de 5 a 50 registros, com opções visuais de 10, 25 e 50;
- a resposta inclui `action_pagination` com página atual, tamanho, total de ações e total de páginas.

### Consistência visual

- temas `system`, `light` e `dark`, persistidos no navegador;
- cor âmbar como assinatura do LCA e azul institucional como estrutura comum;
- informações técnicas e latência somente no modo avançado;
- ações confirmadas não recebem destaque repetitivo; somente exceções são enfatizadas;
- o estado lógico continua calculado por `light_asset_id`, sem duplicar pontos paralelos.

O Database Schema foi atualizado para 16 com colunas aditivas em `lca_light_assets` e a tabela de auditoria `lca_light_merge_log`.

### Alterações do LCA 0.3.6

- cada circuito lógico recebe um `circuit_id` canônico;
- pontos diretos e paralelos referenciam o mesmo circuito real;
- duplicidades seguras são consolidadas com migração de canais, sessões, eventos e efeitos de cenas;
- novas configurações reutilizam circuitos existentes em vez de criar ativos duplicados;
- o dashboard separa circuitos monitorados de pontos de acionamento;
- o modo avançado apresenta indicadores de qualidade da configuração;
- Database Schema `16`.

## LCA 0.3.1 — Interaction Origin Attribution

O tópico canônico `seiden/lca/interactions` carrega a proveniência conhecida pelo Node-RED antes da sincronização de um paralelo ou da execução de uma cena. O Flow resolve o dispositivo e o gang cadastrados, registra a interação separadamente do efeito e correlaciona mudanças da mesma luz lógica em uma janela temporal curta.

Campos suportados: `source_entity`, `source_device`, `source_channel`, `requested_state`, `target_entity`, `circuit_id`, `interaction_kind`, `origin_mode`, `ha_context_id`, `ha_parent_id`, `ha_user_id` e `occurred_at`.

## Identificação

- Serviço: `seiden_flow`
- Versão: `0.15.6`
- LCA: `0.3.6`
- Platform Schema: `2.0`
- Database Schema: `16`
- Porta interna: `8100`
- Persistência: SQLite na pasta de configuração do add-on

## Responsabilidade do FLOW

O FLOW é a camada de entendimento operacional do Seiden One. Ele recebe eventos normalizados, preserva medições, correlaciona causas e efeitos e expõe portais e APIs analíticas.

## Classificador compartilhado de perfis

O módulo `profile_classification.py` centraliza a interpretação dos envelopes ambientais para EEA e TCA. Ele não altera o contrato do Vision nem o `environmental_profiles.json`.

Semântica:

- `optimal`: faixa recomendada;
- `attention`: envelope de tolerância temporária;
- `critical`: limites operacionais externos;
- valor fora de `critical`: condição crítica.

Estados derivados: `ideal`, `attention`, `elevated_alert` e `critical`.

O classificador também valida a ordem:

```text
critical.min <= attention.min <= optimal.min <= optimal.max <= attention.max <= critical.max
```

Perfis incompletos ou fora dessa ordem são marcados como inválidos, sem classificação silenciosa.

## HEA

O Human Experience Analytics consome evidências humanas agregadas e mantém o portal `/hea`. A linha 0.11.x não altera o motor HEA.

## EEA

O Environmental Experience Analytics analisa ambientes voltados a pessoas. O portal `/environment` separa:

- estado atual;
- resumo do período;
- evolução de EEA Index, temperatura e umidade;
- distribuição das condições;
- filtros de local, fonte e período.

O EEA preserva medições ambientais e usa os campos enriquecidos pelo Vision, incluindo perfil, faixas aplicadas, pontuações, condições e motivos.

## TCA 0.2

O Thermal Control Analytics analisa ativos térmicos.

### Ativos

Cada ativo possui:

- `asset_id`;
- nome;
- tipo e perfil;
- faixa ótima derivada do perfil;
- avaliação opcional de umidade;
- metadados e snapshot do perfil aplicado.

### Perfis

O catálogo principal é lido de:

```text
/homeassistant/seiden_vision/environmental_profiles.json
```

Somente perfis com `analysis_type = environmental_compliance` são apresentados no TCA. O arquivo é somente leitura para o FLOW. Há fallback interno caso a configuração autoritativa esteja indisponível.

### Fontes e bindings

As fontes observadas pelo Bridge são catalogadas antes da associação. Um ativo pode ter múltiplas fontes e múltiplas métricas por fonte:

- `temperature`;
- `humidity`;
- `door`;
- `power`;
- `voltage`;
- `current`;
- `energy`.

Cada binding pode declarar um papel operacional e a referência principal de temperatura.

### Episódios

O motor TCA correlaciona eventos de abertura, medições térmicas e potência para produzir sessões com duração, impacto, recuperação e energia integrada. Sem sensor de porta, identifica excursões térmicas e recuperação sem atribuir causalidade. A interface é adaptativa às capacidades disponíveis e o cadastro aceita unidade/filial e área para preparar operações distribuídas. A linha 0.11.x ainda não afirma diagnóstico de falha nem manutenção preditiva por AI.

## Montagens do add-on

O manifesto monta:

- `addon_config` com escrita, para banco e configurações próprias;
- `homeassistant_config` em modo somente leitura, para consumir os perfis mantidos pelo Vision.

## Compatibilidade

A migração para Database Schema 12 é aditiva. Tabelas e dados anteriores são preservados. HEA e EEA continuam disponíveis mesmo sem ativos TCA cadastrados.

## Modular Foundation (0.12.0)

A fundação modular usa `ModuleManifest` e `ModuleRegistry` para declarar e descobrir capacidades analíticas. A versão 0.12.0 não migrou o banco nem alterou contratos existentes: ela cria a fronteira arquitetural que permitirá extrair gradualmente rotas, repositórios, analytics e interfaces de cada módulo.

Cada manifesto declara: identificador, nome, versão interna, estado, eventos consumidos, capacidades, portais, prefixos de API e dependências. Novos módulos devem ser registrados em `app/modules/catalog.py`.

O catálogo de soluções diferencia composições `active` e `planned`; uma composição planejada não significa que seus módulos estejam implementados.


## LCA 0.1.0

O Lighting Context Analytics consome eventos normalizados pelo Bridge, descobre dispositivos sob os prefixos MQTT configurados e cria contexto analítico de iluminação. Não possui APIs de comando. Portal: `/lca`. Prefixo de API: `/api/v1/lca`.

## LCA 0.3.0 — configuração espacial e escopo por canal

- portal com edição de dispositivo e teclas;
- enriquecimento de ambiente, posição, adjacência e direção;
- vínculo com luz/função e grupos de paralelo virtual;
- status automático `discovered`, `incomplete` e `configured`;
- opção explícita para ignorar dispositivos sem relevância analítica;
- nenhuma função de comando ou controle de iluminação.

O LCA mantém o último estado observado de cada canal. A primeira publicação estabelece a linha de base e não gera evento. Publicações seguintes com o mesmo valor contam apenas como mensagens técnicas. Uma mudança real gera `state_change`; ações explícitas do dispositivo geram `interaction`. Sessões são abertas e fechadas somente por transições reais.


## LCA 0.3.0 — Channel Scope Management

- `lca_channels.enabled` define o escopo analítico por canal.
- Canais desativados são descartados antes de `lca_messages`, baseline, eventos e sessões.
- Eventos históricos de canais desativados ficam preservados, mas são excluídos das consultas e dashboards atuais.
- Alterar o estado de monitoramento remove a linha de base e qualquer sessão aberta do canal; a próxima publicação após reativação é apenas baseline.
- O status de configuração considera exclusivamente canais ativos.
- Database Schema permanece em `13`; não há migração estrutural.

## LCA 0.2.1 — ciclo de vida de dispositivos

O LCA permite ignorar, reativar e remover dispositivos. A opção **Ignorar** é indicada quando o Bridge assina um prefixo amplo, mas um dispositivo específico não deve participar da análise. Dispositivos ignorados são descartados antes do registro de mensagens, estados, sessões ou eventos. A remoção pode preservar o histórico e, opcionalmente, bloquear uma nova descoberta.

### Ciclo de vida de dispositivos LCA

- `GET /api/v1/lca/devices/ignored`
- `POST /api/v1/lca/devices/{device_id}/reactivate`
- `DELETE /api/v1/lca/devices/{device_id}`

O `DELETE` aceita `preserve_history` e `ignore_future` no corpo JSON.

## LCA — Home Assistant Direct Points

Flow 0.16.1 / LCA 0.4.0.3 aceita `state_transition` do HA State Driver do
Seiden Bridge.

`Home Assistant entity → Bridge HA State Driver → state_transition → LCA`

Após a primeira transição, a entidade aparece em **Infraestrutura** como fonte
Home Assistant. Configure seu ponto `Estado` como **Controla uma luz diretamente**,
defina nome e ambiente e associe normalmente os gangs Zigbee que funcionam como
paralelos virtuais.


## LCA — Canonical State Authority

A partir do LCA 0.4.0.4, o estado lógico de um circuito só pode ser alterado
por uma transição observada no ponto configurado como **direto**.

`lighting_interaction` registra intenção, origem e correlação, mas nunca grava
o estado canônico do circuito.

Essa regra vale igualmente para pontos diretos vindos do MQTT State Driver e
do HA State Driver.


## Flow 0.16.2 / LCA 0.4.1 — Time Patterns

Esta versão parte da baseline estável **Flow 0.16.1.3 / LCA 0.4.0.6** e adiciona
somente analytics temporais, sem modificar a lógica de ingestão, correlação,
pontos diretos, paralelos virtuais ou estado canônico.

O LCA passa a responder:

- quando cada circuito costuma ser utilizado;
- quanto tempo permanece ligado em cada hora do dia;
- como o uso se distribui pelos dias da semana;
- qual é a faixa típica e o horário de pico;
- como os ambientes se comparam em tempo ligado e sessões.

O heatmap e os agregados são calculados a partir das sessões lógicas já
existentes (`lca_circuit_sessions`) e respeitam o timezone operacional.


## Flow 0.16.2.1 / LCA 0.4.1.1 — UX/UI Refinement

Refinamento da visão administrativa do LCA, sem alterar a baseline analítica
ou a lógica estabilizada de pontos diretos, paralelos, MQTT State Driver e
HA State Driver.

A versão melhora hierarquia e densidade visual com:

- baseline fixa no gráfico de uso por horário;
- heatmap sequencial de intensidade com legenda;
- progressive disclosure em listas extensas;
- Top 5 na comparação entre ambientes;
- 5 ações recentes por página como padrão;
- configuração administrativa recolhida por padrão.

Toda a profundidade administrativa permanece disponível sob demanda.


## Flow 0.16.3 / LCA 0.4.2 — Interaction Preference

O LCA passa a quantificar como os usuários preferem acionar cada circuito.
A análise é calculada sobre `lca_events` consolidados e não interfere na
ingestão ou correlação operacional.

Principais leituras:

- ranking de pontos mais usados;
- direto, paralelo e cena;
- origem local, remota, automação e desconhecida;
- ponto dominante por circuito;
- comparação com o período anterior de mesma duração.

Endpoint dedicado: `/api/v1/lca/interaction-preference`.


## Flow 0.17.0 / LCA 0.5.0 — Behavioral Patterns

O Behavioral Patterns aprende a rotina operacional a partir de
`lca_circuit_sessions`. A camada é somente leitura e não altera o pipeline
de ingestão/correlação.

### Confiança

Cada padrão recebe um nível de confiança calculado a partir de três sinais:

1. tempo observado;
2. quantidade de sessões;
3. consistência estatística do comportamento.

A interface usa quatro estados: `Em aprendizado`, `Baixa confiança`,
`Confiança moderada` e `Alta confiança`.

### Capacidades

- perfil robusto de duração por circuito;
- faixa típica de horário de início;
- sequências recorrentes em janela de 10 minutos;
- uso simultâneo por sobreposição de sessões;
- desvios conservadores de duração, horário e frequência.

Endpoint: `/api/v1/lca/behavioral-patterns`.

Nenhuma tabela nova é criada; database schema permanece 19.


## Flow 0.17.0.1 / LCA 0.5.0.1 — MQTT State Driver topic compatibility

`state_transition` MQTT vindo do Seiden Bridge já é resultado de uma seleção
explícita em `state_driver_topics`. Por isso, o LCA não reaplica
`lca_topic_prefixes` sobre esse evento canônico.

O filtro de prefixos permanece ativo para MQTT bruto.


## Flow 0.18.0 / TCA 0.6.0 — UX Foundation

O TCA passa a ter três perspectivas sobre a mesma base de dados:

- **Operação** — Exceptions First e leitura rápida, otimizada para acompanhamento diário e tablets.
- **Executivo** — condição agregada e prioridades atuais.
- **Análise** — experiência completa já existente, com período, envelope térmico, porta, energia, sessões e configuração.

Nenhuma perspectiva restringe outra. Um tablet pode abrir toda a análise, e um desktop
pode permanecer em Operação. A preferência é lembrada no navegador.

Não há multi-site nesta release e não há mudança no backend analítico do TCA.


## Flow 0.19.0 — Global UX Foundation

A camada visual do Flow passa a compartilhar duas preferências persistentes entre
o dashboard principal e os portais HEA, EEA, TCA e LCA:

- `seiden-flow-language`: `pt-BR` ou `en-US`;
- `seiden-flow-theme`: `light`, `system` ou `dark`.

A internacionalização é aplicada exclusivamente na camada de apresentação. Valores
de domínio, APIs, payloads, banco e lógica analítica não são traduzidos nem alterados.
Datas e números apresentados pela UI usam o locale escolhido.

O TCA recebe somente a camada visual necessária para dark mode. Suas perspectivas
Operação, Executivo e Análise, bem como todo o backend térmico, permanecem inalterados.
O LCA mantém compatibilidade com a antiga chave local `seiden_theme` apenas para
migração da preferência, passando a persistir o valor na chave global.

Database schema permanece 19.


## Flow 0.19.0.1 — Translation & Controls Polish

Presentation-only patch over 0.19.0. Language and appearance selectors now follow the same visual convention in all portals. English translation coverage was expanded to dynamic content, tooltips, placeholders and runtime text updates. No analytics, storage, API, MQTT, ingestion or business-rule logic changed.


## Flow 0.19.0.3 — Complete i18n Runtime Polish

Presentation-only patch over 0.19.0.1. A second full PT/EN audit hardened runtime translation for compound labels, dynamic counters, singular/plural grammar, relative-time phrases, weekday abbreviations, configuration labels and module-generated messages across FLOW, HEA, EEA, TCA and LCA. User-defined entity names remain untouched. No analytics, storage, API, MQTT, ingestion or business-rule logic changed.

## Flow 0.20.1 — ITA 0.1.0

### Infrastructure Telemetry Analytics
O ITA consome eventos canônicos `infrastructure.telemetry_snapshot` produzidos pelo Seiden Bridge. O módulo não depende de fabricante nem de IDs específicos de sensores: classifica telemetria por `physical_context`, unidade, saúde, thresholds e relações do modelo Redfish.

Portal: `/ita`

APIs:
- `GET /api/v1/ita/systems`
- `GET /api/v1/ita/portfolio`
- `GET /api/v1/ita/systems/<system_id>/current`
- `GET /api/v1/ita/systems/<system_id>/history?hours=24`

A versão 0.1.0 persiste snapshots e medições, calcula deltas Ambiente→Intake, Intake→CPU e Intake→Exhaust, preserva limites nativos, acompanha potência e ventilação e apresenta histórico térmico. Baselines comportamentais e detecção de anomalias serão evoluções posteriores, após formação de histórico suficiente.


## Flow 0.20.2 — ITA 0.1.2 · Asset Lifecycle

O ITA passa a separar a existência histórica do ativo de sua visibilidade operacional. Um sistema pode ser `active`, `hidden` ou `decommissioned` sem qualquer exclusão de snapshots, measurements ou eventos. A visão padrão do portfólio retorna apenas ativos `active`; filtros permitem consultar todos os estados. Alterações de status são auditadas em `ita_events`. Telemetria posterior continua sendo persistida e não reativa o ativo automaticamente. Database schema: 22.


## Flow 0.21.0 — ITA 0.2.0 · Adaptive Infrastructure Telemetry

O ITA passa a representar telemetria de infraestrutura de forma adaptativa. O portal detecta as capacidades presentes no snapshot e apresenta somente os domínios aplicáveis: compute, memória, storage, rede, térmica, energia/refrigeração e disponibilidade. Fontes Redfish e Linux podem coexistir no mesmo portfólio. Thresholds nativos continuam prioritários; guardrails do Flow são aplicados apenas quando a fonte não fornece limites e somente para métricas percentuais amplamente interpretáveis.

## Flow 0.22.0 — ITA 0.3.0 · Fleet

Configuração no App:

```yaml
ita_fleet_enabled: true
ita_fleet_receiver_url: "http://192.168.4.134:8787"
ita_fleet_read_token: "TOKEN_DE_LEITURA_DO_RECEIVER"
ita_fleet_timeout_seconds: 8
ita_fleet_refresh_seconds: 30
```

O `ita_fleet_read_token` é usado apenas pelo backend do Flow e não é exposto
ao JavaScript do portal.

Rotas:

- `/ita` — ITA adaptativo/local.
- `/ita/fleet` — visão consolidada dos CASTs.
- `/api/v1/ita/fleet` — proxy protegido internamente pelo Flow.
- `/api/v1/ita/fleet/<pulse_id>` — detalhe canônico.

## Flow 0.22.1 — ITA 0.3.1 · Unified Assets

O ITA passa a usar uma única superfície:

- `/ita` — servidores locais e CAST/Pulse unificados.
- `/ita/fleet` — alias legado que abre a mesma tela.
- `/api/v1/ita/fleet` e `/api/v1/ita/fleet/<pulse_id>` — mantidos como proxy
  server-side para o Receiver.

A configuração do Receiver permanece igual:

```yaml
ita_fleet_enabled: true
ita_fleet_receiver_url: "http://192.168.4.134:8787"
ita_fleet_read_token: "TOKEN_DE_LEITURA_DO_RECEIVER"
ita_fleet_timeout_seconds: 8
ita_fleet_refresh_seconds: 30
```

O token de leitura nunca é exposto ao navegador.

## Flow 0.22.1.1 — Startup Memory Fix

A migração legado → schema atual agora consome `events` em lotes de 250,
evitando carregar todo o histórico em RAM durante o startup.

Logs esperados:

```text
[STARTUP] Legacy migration: streaming events in batches of 250
[STARTUP] Legacy migration: 1000 events processed
...
[STARTUP] Legacy migration complete: N events processed
```

Nenhuma lógica do ITA 0.3.1 foi alterada.

## Flow 0.22.1.2 — ITA 0.3.1.1 · UX/UI Polish

Ajustes exclusivamente de apresentação/semântica no detalhe CAST:

- capabilities humanizadas e sem duplicações;
- estados de Apps localizados;
- runtime agregado dos Apps explicitado;
- tráfego e I/O identificados como contadores acumulados;
- temperatura com indicação da entidade fonte;
- diagnóstico da Pulse recolhível.

Nenhuma API ou lógica de ingestão foi alterada.

## Flow 0.22.1.3 — ITA 0.3.1.2 · Pulse Asset Lifecycle

O detalhe de ativos Seiden Pulse passa a oferecer a mesma gestão de lifecycle
dos demais ativos ITA:

- Ativo
- Oculto
- Descomissionado
- Exclusão definitiva (zona de risco)

O Flow apenas faz proxy server-side para a API privada do Receiver 0.2.3.
O `read_token` nunca é enviado ao navegador.

Para instalações novas:

```yaml
ita_fleet_receiver_url: "http://192.168.4.134:8788"
```

## Flow 0.22.1.4 — ITA 0.3.1.3 · Observability UX

Hierarquia padrão do detalhe de um ativo:

1. Cabeçalho, saúde e freshness
2. Problemas/alertas ativos — somente quando houver
3. KPIs e capacidades disponíveis
4. Histórico/evolução quando suportado
5. Diagnóstico técnico recolhível
6. Gestão do ativo recolhível no final

A visão geral ordena ativos automaticamente pela necessidade de atenção.

## Flow 0.22.1.5 — ITA 0.3.1.4 · Zigbee Device-Level Alert Details

Compatível com Pulse 0.1.1.4.

O Flow consome dos alertas do Receiver:
- `missing_devices_detail`
- `offline_devices_detail`
- `new_devices_detail`

Quando `zigbee_send_names: true`, o friendly name é o identificador principal
mostrado na tela. IEEE permanece como contexto técnico.

A interface limita a lista a 5 devices por grupo e mostra `+ N outros` quando
necessário.

## Flow 0.22.1.6 — ITA 0.3.1.5 · Linux Host UX

- Reconhecimento explícito de `linux_host` proveniente da Seiden Pulse Linux.
- Detalhe capability-aware para CPU/load, memória/swap, disco, uptime, processos,
  rede, sistema operacional/kernel/arquitetura e serviços configurados.
- Blocos exclusivos de HAOS/CAST não são renderizados em hosts Linux.
- Temperatura só é exibida quando a capability térmica realmente existe.
- Backend ITA, APIs, banco e lifecycle permanecem inalterados.

## Flow 0.22.1.7 — ITA 0.3.1.6 · Smart Overview Filters

- Cards de resumo da home funcionam como filtros operacionais clicáveis.
- A seleção é preservada em `sessionStorage` e possui feedback visual/acessível.
- As contagens continuam representando todo o conjunto da visão de lifecycle atual.
- A grade abaixo mostra apenas o estado operacional selecionado.
- `linux_host` deixa de receber cards sem sentido como `Apps 0/0` na home.

## Flow 0.22.1.8 — ITA 0.3.1.7 · Release Integrity

- Auditoria completa dos metadados de release após a 0.22.1.7.
- `config.yaml`, `app/version.py`, manifest ITA e footers sincronizados.
- README e documentação corrigidos para refletir as funcionalidades das releases corretas.
- Histórico completo do CHANGELOG restaurado a partir da baseline 0.22.1.5.
- Nenhuma alteração de backend, API, banco ou lifecycle.
