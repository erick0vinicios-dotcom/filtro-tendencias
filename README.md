# Filtro de tendências gringas

Coleta automática de tendências de SaaS e ferramentas de IA/automação em crescimento nos EUA, com pontuação por evidência de crescimento e de retorno financeiro.

## Rodar localmente

Requer Python 3.11 ou mais novo. Não há dependências externas.

```
python -m collector
python -m collector --only hackernews
```

Para testar localmente as fontes que pedem token, copie `.env.example` para `.env` e preencha. O `.env` fica fora do git; no GitHub Actions os tokens vêm dos Secrets.

Os resultados brutos de cada fonte ficam em `data/raw/`. Pesos, limites e fontes ativas ficam em `config.toml`.

O briefing completo do projeto está em [CLAUDE.md](CLAUDE.md).
