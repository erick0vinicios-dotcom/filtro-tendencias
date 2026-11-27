# Projeto: Filtro de tendências gringas — v1 automatizada

## Contexto
Projeto pessoal, não comercial. Objetivo: um fluxo automatizado que encontra tendências de SaaS e ferramentas de IA/automação que estão crescendo nos EUA, pontua cada uma por evidência de crescimento e de retorno financeiro, e mostra o resultado num painel web atualizado automaticamente. Nenhuma coleta manual.

## Decisões já tomadas
- Orçamento zero: só APIs e infraestrutura gratuitas.
- Mercado de origem: EUA. Categoria inicial: SaaS e ferramentas de IA/automação.
- Repositório público no GitHub (Actions e Pages gratuitos; os dados coletados já são públicos).
- Coleta agendada no GitHub Actions a cada 3 horas.
- Painel estático no GitHub Pages lendo JSON gerado pela coleta.

## Fontes da v1
1. Hacker News (Show HN): API oficial Firebase, sem autenticação (https://hacker-news.firebaseio.com/v0/showstories.json e /v0/item/{id}.json). Busca histórica via Algolia (https://hn.algolia.com/api/v1/search?tags=show_hn).
2. Product Hunt: API v2 GraphQL (https://api.producthunt.com/v2/api/graphql), token de desenvolvedor no segredo PRODUCTHUNT_TOKEN. Uso não comercial é permitido; respeitar os limites de taxa informados nos cabeçalhos.
3. GitHub: API oficial de busca (/search/repositories), repositórios de IA criados recentemente e ordenados por estrelas, usando o GITHUB_TOKEN do Actions. A página Trending não tem API e não deve ser raspada.
4. TrustMRR (receita verificada por provedor de pagamento): ANTES de implementar, ler https://trustmrr.com/llms.txt e os termos de uso. O site oferece versões .md das páginas (https://trustmrr.com/startup/{slug}.md). Só coletar se os termos permitirem; caso contrário, deixar a fonte desligada e me avisar.

Fora da v1: Google Trends (sem API gratuita oficial), Reddit (API pública fechando em março de 2027), ferramentas pagas de estimativa de apps.

## Pontuação (método inicial, ajustável)
- Pesos e limites num arquivo de configuração separado, para eu ajustar sem mexer no código.
- Unificar o mesmo produto entre fontes pelo domínio normalizado da URL.
- Filtrar a categoria SaaS/IA por tópicos e palavras-chave configuráveis.
- Sinais: velocidade dentro de cada fonte (pontos, votos ou estrelas por hora, normalizada por percentil na fonte), presença em mais de uma fonte, receita verificada.
- Nível de evidência de retorno: Verificada (TrustMRR), Hipótese (sem evidência). Nunca inventar receita.
- Confiança: Alta = receita verificada e presença em 2+ fontes; Média = um dos dois; Baixa = só sinais de atenção.
- Popularidade sozinha nunca vira confiança alta.

## Dados
- data/latest.json com o ranking atual e o horário da última coleta.
- data/history/AAAA-MM-DD.json com fotografias diárias, para calcular crescimento ao longo do tempo com período explícito.
- Cada item guarda: nome, URL, descrição, fontes com link e métrica bruta, data da coleta, pontuação, confiança e evidência de retorno.

## Painel
- Página estática publicada pelo GitHub Pages via Actions.
- Tabela ordenada pela pontuação, com filtros por fonte, confiança e evidência de retorno, busca por nome, link para cada evidência e o horário da última atualização bem visível.
- Funcionar bem no celular.

## Robustez
- Uma fonte que falhar não pode derrubar as outras; registrar o erro e seguir.
- Logs da execução mostrando a etapa atual e qual fonte/item está sendo processado.
- Não commitar se nada mudou.
- Nenhum token no código; tudo em GitHub Secrets.

## Como trabalhar comigo
- Código limpo, sem comentários.
- Ao entregar cada script, explicar o que ele faz, a lógica principal e as escolhas técnicas.
- Estou aprendendo DevOps: em cada passo (Actions, segredos, Pages, cron), explicar o porquê, não só o comando.
- Antes de pedir acesso a um site, serviço ou permissão, explicar o que será feito lá.
- Salvar este briefing como CLAUDE.md na raiz do repositório.

## Entregas, em ordem
1. Estrutura do repositório e coletor do Hacker News rodando localmente.
2. Coletores do Product Hunt e do GitHub; verificação dos termos do TrustMRR e, se permitido, seu coletor.
3. Unificação, pontuação e geração dos JSON.
4. Workflow do GitHub Actions agendado a cada 3 horas.
5. Painel no GitHub Pages.
6. Revisão final: rodar o fluxo de ponta a ponta e me mostrar o painel com dados reais.
