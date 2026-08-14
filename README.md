# Seiden FLOW 0.23.1

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
