# TireControl Web (Next.js + Supabase)

O novo sistema web do TireControl, migrado do legado em Streamlit para uma arquitetura moderna e escalável.

## 🏗 Arquitetura

- **Frontend**: Next.js 14+ (React, Tailwind CSS, TypeScript).
- **Backend**: Supabase (PostgreSQL, Auth, Edge Functions, RPCs).
- **Legacy**: O código em `legacy/streamlit` serve apenas para consulta e pode ser descontinuado.

## ✨ Módulos Implementados

1.  **Rodízio Visual (`/rodizio`)**:
    -   Interface visual de arrastar/clicar para pneus.
    -   Sugestões automáticas baseadas em desgaste.
    -   **IA Integration**: Análise de rodízio com inteligência artificial.

2.  **Recapagem (`/recapagem`)**:
    -   Envio de pneus para recapadoras.
    -   Controle de ordens ativas.
    -   Retorno de pneus para o estoque.

3.  **Análise de CPK (`/analise/cpk`)**:
    -   Cálculo estatístico de capacidade do processo (Qualidade).
    -   Histograma de vida útil e recomendações automáticas.

4.  **Relatórios (`/relatorios`)**:
    -   Visão geral da frota (Pizza).
    -   Movimentações recentes (Barras).
    -   Estimativa de custos.

## 🚀 Como Rodar (Locamente)

1.  Instale as dependências:
    ```bash
    cd apps/web
    npm install
    ```

2.  Configure o `.env.local` na pasta `apps/web`:
    ```env
    NEXT_PUBLIC_SUPABASE_URL=sua_url
    NEXT_PUBLIC_SUPABASE_ANON_KEY=sua_chave
    ```

3.  Rode o servidor de desenvolvimento:
    ```bash
    npm run dev
    ```

## 📦 Deploy

O projeto é compatível com:
-   **Vercel** (Recomendado para performance máxima).
-   **GitHub Pages** (via GitHub Actions, para hospedagem estática gratuita).
-   **Docker / Self-hosted**.

## 🛠 Banco de Dados (Supabase)

Certifique-se de aplicar as migrations na ordem:
1.  `infra/supabase/migrations/2026-02-12_web_supabase_rpc_v2.sql`
2.  `infra/supabase/migrations/2026-02-12_web_supabase_rpc_v3_retorno.sql`
3.  `infra/supabase/migrations/20260214_rpc_rodizio.sql`
4.  `infra/supabase/migrations/20260215_cpk_reports.sql`
