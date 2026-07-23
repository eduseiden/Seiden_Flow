# Changelog

## 0.3.0
- Novo módulo Human Experience Analytics (HEA).
- Novo Observation Engine genérico.
- Novas entidades `Observation` e `ObservationAggregate`.
- Consumo automático de `vision.analysis_completed`.
- Separação entre expressão observada e identidade da pessoa.
- Remoção da emoção do evento técnico persistente do Vision.
- Retenção curta e limpeza automática das observações brutas.
- Agregação configurável por janela de tempo e fonte.
- Quantidade mínima de amostras configurável; abaixo do limite, o dashboard mostra dados insuficientes.
- Confiança mínima configurável.
- Experience Index de -100 a +100.
- Dashboard HEA com índice, distribuição, confiança, amostras e ranking por fonte.
- Novas APIs `/api/v1/hea/*` e `/api/v1/observations`.
- Nova entidade `sensor.seiden_flow_experience_index` no Home Assistant.
- Migração automática e não destrutiva do banco para o schema 3.

## 0.2.1
- Dashboard atualizado automaticamente a cada 5 segundos.
- Temas Escuro, Claro e Automático.

## 0.2.0
- Modelo de domínio e migração automática do banco.

## 0.1.0
- Primeira versão da camada de dados operacional.
