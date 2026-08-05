# Seiden FLOW 0.15.3 — Documentação técnica

## LCA 0.3.3 — Logical State & Experience Redesign

O dashboard separa ações de negócio de telemetria técnica. Interações são exibidas como eventos-pai e carregam os efeitos correlacionados em `effects`; mudanças brutas permanecem em `technical_events` e somente aparecem no modo avançado. Nenhuma estrutura de banco foi alterada.

O endpoint `/api/v1/lca/dashboard` passa a expor também `recent_actions`, `technical_events`, `confirmed_interactions` e `unconfirmed_interactions`, preservando `recent_events` para compatibilidade.

### Estado lógico consolidado e experiência visual

- `active_lights` é calculado por `light_asset_id`, usando o estado mais recente entre os pontos ativos associados;
- gangs diretos e paralelos não são somados como luzes distintas;
- `current_lights` expõe estado, ambiente, quantidade de pontos e última atualização por circuito;
- `origin_breakdown` e `role_breakdown` alimentam as análises do período;
- o portal utiliza terminologia comercial na visão padrão e reserva identificadores técnicos ao modo avançado.

## LCA 0.3.1 — Interaction Origin Attribution

O tópico canônico `seiden/lca/interactions` carrega a proveniência conhecida pelo Node-RED antes da sincronização de um paralelo ou da execução de uma cena. O Flow resolve o dispositivo e o gang cadastrados, registra a interação separadamente do efeito e correlaciona mudanças da mesma luz lógica em uma janela temporal curta.

Campos suportados: `source_entity`, `source_device`, `source_channel`, `requested_state`, `target_entity`, `circuit_id`, `interaction_kind`, `origin_mode`, `ha_context_id`, `ha_parent_id`, `ha_user_id` e `occurred_at`.

## Identificação

- Serviço: `seiden_flow`
- Versão: `0.15.3`
- LCA: `0.3.3`
- Platform Schema: `2.0`
- Database Schema: `15`
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
