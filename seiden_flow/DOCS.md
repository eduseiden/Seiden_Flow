# Seiden FLOW 0.8.0

Camada de compreensão do Seiden One. Transforma evidências em entendimento operacional.

## Environmental Storage

A persistência ambiental, introduzida na versão 0.7.1, adiciona suporte nativo ao evento `environment.observation`, produzido pelo Seiden Vision. A versão 0.8.0 consolida a numeração do add-on, do runtime e da documentação, sem alterar os contratos existentes.

O fluxo ambiental passa a ser:

```text
MQTT → Seiden Bridge → Seiden Vision → environment.observation → Seiden FLOW
```

### Dados armazenados

- temperatura normalizada em Celsius;
- umidade relativa em percentual;
- condição ambiental;
- Environmental Comfort Score;
- confiança e ruleset da análise;
- fonte, local, conexão e tópico MQTT;
- bateria, qualidade do enlace e último contato da fonte;
- correlação com o evento original por `source_event_id`.

O FLOW impede duplicidades por `event_id` e `source_event_id`.

### APIs ambientais

- `GET /api/v1/environment/measurements`
- `GET /api/v1/environment/latest`
- `GET /api/v1/environment/summary`

Esta versão implementa a camada de armazenamento. O painel público do EEA será introduzido em uma versão posterior.

## Operação e Inteligência

O painel principal permanece separado em:

- **Operação**: ocorrências, pessoas no local, fontes e enriquecimentos do Vision;
- **Inteligência**: catálogo das soluções analíticas, começando pelo Human Experience Analytics.

Uma ocorrência do Bridge conta uma vez. `vision.analysis_completed` é armazenado como evidência correlacionada por `source_event_id`, sem aumentar o contador de ocorrências. O portal público do HEA permanece disponível em `/hea`.

## Eventos consumidos

- `seiden_bridge_event`
- `seiden_connection_online`
- `seiden_connection_offline`
- `vision.analysis_completed`
- `environment.observation`

Mensagens brutas `mqtt.message_received` permanecem disponíveis para diagnóstico, mas não são contabilizadas como ocorrências operacionais.
