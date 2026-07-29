# Seiden FLOW 0.8.1.2

Camada de compreensão do Seiden One. Transforma evidências em entendimento operacional.

## Environmental Experience Analytics — EEA

A versão 0.8.1.2 consolida o primeiro motor analítico ambiental do FLOW. As medições brutas continuam preservadas integralmente no banco; para os cálculos, o EEA mantém somente a última leitura de cada fonte em cada janela temporal, evitando que republicações MQTT distorçam médias, tendências e distribuição das condições.

O fluxo ambiental é:

```text
MQTT → Seiden Bridge → Seiden Vision → environment.observation → Seiden FLOW → EEA
```

### Indicadores calculados

- EEA Index médio de 0 a 100;
- condição e leitura ambiental atuais;
- médias, mínimos e máximos de temperatura, umidade e Comfort Score;
- distribuição entre `comfortable`, `attention` e `uncomfortable`;
- comparação com o período imediatamente anterior;
- tendência `improving`, `stable`, `worsening` ou `insufficient_data`;
- melhor e pior intervalo analítico;
- qualidade dos dados, cobertura, confiança e amostras brutas/normalizadas.

### APIs ambientais

- `GET /api/v1/environment/measurements`
- `GET /api/v1/environment/latest`
- `GET /api/v1/environment/summary`
- `GET /api/v1/environment/analytics`
- `GET /api/v1/environment/timeline`

### Filtros do EEA

Os endpoints analíticos aceitam:

- `period`: `1h`, `6h`, `12h`, `24h`, `7d` ou `30d`;
- `start` e `end`: intervalo UTC personalizado em ISO 8601;
- `source_id` e `location_id`;
- `sampling_minutes`: janela de normalização, de 1 a 60 minutos;
- `bucket_minutes`: agrupamento da timeline, de 1 a 1440 minutos.

Exemplos:

```text
/api/v1/environment/analytics?period=24h
/api/v1/environment/analytics?location_id=escritorio&period=7d
/api/v1/environment/timeline?period=24h&bucket_minutes=15
```

O dashboard público do EEA permanece planejado para uma versão posterior.

## Environmental Storage

O armazenamento nativo do evento `environment.observation` preserva:

- temperatura em Celsius e umidade relativa;
- condição ambiental, Comfort Score, confiança e ruleset;
- fonte, local, conexão e tópico MQTT;
- bateria, qualidade do enlace e último contato;
- correlação por `source_event_id`.

O FLOW impede duplicidades técnicas por `event_id` e `source_event_id`.

## Operação e Inteligência

O painel principal permanece separado em:

- **Operação**: ocorrências, pessoas no local, fontes e enriquecimentos do Vision;
- **Inteligência**: catálogo das soluções analíticas, incluindo HEA e EEA.

O portal público do HEA permanece disponível em `/hea`.

## Eventos consumidos

- `seiden_bridge_event`
- `seiden_connection_online`
- `seiden_connection_offline`
- `vision.analysis_completed`
- `environment.observation`

## Consistência dos indicadores agregados

Na versão 0.8.1.2, a condição exibida nos períodos agregados é derivada do `comfort_score` médio: `comfortable` (85–100), `attention` (70–84,99), `uncomfortable` (50–69,99) e `critical` (0–49,99). A distribuição usa as mesmas faixas. O campo `observed_minutes` representa somente minutos com amostras normalizadas; intervalos sem dados não são tratados como tempo medido.

### Consistência da condição atual

No endpoint `/api/v1/environment/analytics`, o bloco `current` aplica o mesmo ruleset do EEA usado na timeline e nos agregados. O valor original recebido do Vision é preservado em `source_condition`, enquanto `condition_source` identifica a classificação oficial como `eea_ruleset`.
