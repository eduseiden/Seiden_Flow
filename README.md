# Seiden FLOW 0.22.1.8

## ITA 0.3.1.7 — Smart Overview Filters + Release Integrity

Evolução da visão geral do Infrastructure Telemetry Analytics com foco em
navegação operacional e consistência de release.

### Destaques

- Cards de resumo `Ativos`, `Normais`, `Atenção`, `Críticos` e `Sem telemetria`
  funcionam como filtros clicáveis.
- Filtro operacional é preservado durante a sessão.
- Estado selecionado recebe feedback visual e `aria-pressed`.
- Estado vazio possui mensagem contextual por filtro.
- Cards de ativos Linux são capability-aware e não exibem `Apps 0/0`.
- Em Linux, `Uptime` e `Disco` permanecem disponíveis na visão geral quando
  presentes no resumo; CPU e memória aparecem quando a resposta Fleet as expõe.
- Detalhe `linux_host` preserva a UX específica introduzida em 0.22.1.6.
- Metadados de versão, footers e documentação foram auditados e sincronizados.
- Histórico completo do CHANGELOG foi restaurado.

Backend, APIs, banco, lifecycle e demais módulos permanecem inalterados.
