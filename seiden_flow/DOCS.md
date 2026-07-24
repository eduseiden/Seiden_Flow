# Seiden FLOW 0.3.1

Camada de dados e inteligência operacional da plataforma Seiden.

## Human Experience Analytics (HEA)

A versão 0.3.1 recebe do Seiden Vision observações de expressões faciais e produz indicadores agregados por fonte e intervalo de tempo.

Princípios:

- a expressão não é persistida junto à pessoa;
- o evento técnico do Vision é armazenado sem `dominant_emotion` e sem a distribuição detalhada de emoções;
- observações brutas não contêm pessoa, foto, biometria ou correlação com o Bridge;
- observações brutas são eliminadas após o período configurado;
- agregados só são publicados quando atingem `human_experience_minimum_samples`;
- o produto apresenta expressões faciais observadas, não afirma conhecer o estado emocional interno da pessoa.

## Integração com o Seiden Vision

Configure no Vision:

```yaml
webhook_enabled: true
webhook_url: http://IP_DO_FLOW:8100/api/v1/events
webhook_api_key: CHAVE_DO_FLOW
```

Se `api_key` estiver vazio no FLOW, a chave do webhook também pode ficar vazia.

O evento esperado é `vision.analysis_completed`. O FLOW extrai `analysis.dominant_emotion`, confiança, origem e horário, converte a emoção em `positive`, `neutral`, `negative` ou `uncertain` e remove a emoção do evento técnico antes de persistir esse evento.

## Configurações do HEA

```yaml
observation_engine_enabled: true
observation_retain_raw_minutes: 30
human_experience_enabled: true
human_experience_minimum_samples: 10
human_experience_aggregation_window_minutes: 15
human_experience_minimum_confidence: 0.75
human_experience_enabled_sources: []
human_experience_positive_weight: 1.0
human_experience_neutral_weight: 0.0
human_experience_negative_weight: -1.0
```

Lista vazia em `human_experience_enabled_sources` habilita todas as fontes. Quando preenchida, somente os `source_id` informados participam.

## Experience Index

Escala de -100 a +100:

- positiva: +1;
- neutra: 0;
- negativa: -1.

As ponderações podem ser alteradas nas opções do add-on.

## APIs

- `POST /api/v1/events`: ingestão canônica, incluindo eventos do Vision;
- `POST /api/v1/observations`: ingestão direta de uma observação anônima;
- `GET /api/v1/hea/summary`;
- `GET /api/v1/hea/history`;
- `GET /api/v1/hea/sources`;
- `GET /api/v1/hea/dashboard`;
- `GET /api/v1/dashboard-data`: dashboard consolidado, agora incluindo HEA.

## Modelo de domínio

Além de Organization, Site, Location, Source, Person, Event e Presence, entram:

- **Observation**: observação anônima temporária;
- **ObservationAggregate**: indicador agregado permanente.


## Portal web HEA (0.4.0)

A página externa está disponível em `http://HOST:8100/hea`. Para publicação remota, aponte um hostname do Cloudflare Tunnel para `http://IP_DO_HOME_ASSISTANT:8100` e proteja-o com Cloudflare Access.

O endpoint utilizado pela página é `GET /api/v1/public/hea/dashboard`. Ele usa uma lista explícita de campos e não expõe nomes de pessoas, imagens, biometria, identificadores de autenticação ou eventos individuais.

Opções principais: `hea_portal_enabled`, `hea_portal_title`, `hea_portal_subtitle`, `hea_portal_default_hours`, `hea_portal_refresh_seconds`, `hea_portal_show_sources`, `hea_portal_privacy_notice` e `hea_portal_allowed_origins`.


## Publicação segura por hostname (0.4.1)

Para publicar somente o portal HEA em um domínio externo, configure:

```yaml
hea_public_hostname: hea.smarthome.app.br
hea_public_restrict_routes: true
```

No Cloudflare Tunnel, o serviço deve apontar apenas para a origem, sem caminho:

```text
http://192.168.4.134:8100
```

Com essa configuração:

- `https://hea.smarthome.app.br/` redireciona para `/hea`;
- `/hea` e `/api/v1/public/hea/dashboard` permanecem disponíveis;
- todas as demais rotas retornam `404`;
- o acesso local por IP continua exibindo o FLOW completo.
