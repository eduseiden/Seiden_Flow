# Seiden FLOW 0.2.1

Camada de dados operacional da plataforma Seiden.

## Modelo de domínio

- **Organization**: organização proprietária dos dados.
- **Site**: instalação física pertencente à organização.
- **Location**: local hierárquico ou ponto de acesso.
- **Source**: produtor do dado, como leitor, câmera ou sistema.
- **Person**: identidade operacional independente do nome exibido.
- **Event**: fato imutável recebido pelo FLOW.
- **Presence**: estado atual derivado dos eventos.

Na primeira inicialização, a versão 0.2.0 migra automaticamente o banco criado pela 0.1.0.

## Entrada canônica

`POST /api/v1/events`

## APIs de domínio

- `GET /api/v1/domain/organizations`
- `GET /api/v1/domain/sites`
- `GET /api/v1/domain/locations`
- `GET /api/v1/domain/sources`
- `GET /api/v1/domain/persons`
- `GET /api/v1/domain/presences`

## Compatibilidade

As APIs `/api/v1/events`, `/api/v1/state/*`, `/api/v1/summary` e as exportações JSON/CSV continuam disponíveis.


## Dashboard 0.2.1

- Atualização automática a cada 5 segundos sem recarregar a página.
- Botão de atualização manual e indicador da última sincronização.
- Polling pausado quando a aba fica em segundo plano.
- Temas Escuro, Claro e Automático, com preferência salva no navegador.
- Endpoint consolidado: `GET /api/v1/dashboard-data`.
