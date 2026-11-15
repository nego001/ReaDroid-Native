# NegrecoDroid P7 — pacote de atualização consolidado

**Data:** 2026-10-20  
**Versão Android:** `3.0.0-preview.4-p7` (`versionCode=4`)  
**Branch de entrega:** `feature/p7-negrecodroid-visual-foundation`  
**Pull request:** [#13](https://github.com/nego001/ReaDroid-Native/pull/13)  
**Issue mestre da interface:** [#11](https://github.com/nego001/ReaDroid-Native/issues/11)  
**Status:** **PRÉVIA TESTÁVEL, NÃO ACEITA COMO VISUAL 1:1 FINAL**.

## O que esta atualização realmente implementa

### Home
- Marca `NegrecoDroid` exclusiva da Home (não duplicada sobre Explorer e Design); nome do launcher corrigido.
- Boas-vindas e mascote vetorial nativo, componentes compactos para respeitar o viewport.
- Quatro cartões com labels `Projetos`, `Arquivos`, `APKs Builds`, `Ameaças` na ordem da arte.
- Estatísticas ligadas ao relatório da sessão quando existem. Builds e ameaças permanecem com travessão enquanto não houver contadores/varreduras comprovados; **nunca exibir `0 Ameaças` sem análise real**.
- Um registro de projeto ativo, sem inventar projetos recentes; navegação real para Arquivos.
- Seis ações rápidas em 3 colunas × 2 linhas, ordenadas como na imagem. Decompilação/assinatura não são falsamente executadas.

### Explorador
- Cabeçalho independente, informações do APK atual, número de edições, breadcrumb clicável.
- Chips de filtros mais usados e menu de filtros adicionais, componentes de arquivo/pasta vetoriais.
- Busca, prévia, plano de edições, paginação via SQLite em lotes de 120 entradas e fallback preservados.
- Mantém SAF, exportação, leitura técnica e arquivo original imutável.

### Design Studio
- Aba principal própria, com **Temas / Layout / Ícones / Logotipo** e navegação inferior do mockup: `Início / Arquivos / Segurança / Build / Design`.
- Quatro primeiros temas com seleção, confirmação, gravação e recarga efetiva das preferências.
- Três layouts reais (`Padrão`, `Compacto`, `Moderno`), ajustando densidade/bordas.
- Cinco presets (`Dark OLED`, `Cyber Neon`, `Minimal`, `Glass`, `Retro`) que gravam combinações da paleta V3. `Glass` é aparência temática, sem blur real.
- Galerias horizontais de previews Android, barra de seleção acessível, duas cartas de ferramentas criativas lado a lado.
- Controles avançados e módulo IA deslocados para Design para liberar espaço na Home, sem apagar suas ações.
- Exportação/importação JSON versão 1 aceita `layout_variant` e `p7_active_preset` com validação estrita e compatibilidade com arquivos legados.

### Identidade e segurança de atualização
- Logotipo SVG editável, símbolo adaptativo do Android e variante monocromática; ícones de Build e Design corrigidos para chave e paleta.
- **APK QA paralelo:** `com.readroid.app.qa` / `NegrecoDroid V3 Teste`. Não substitui a instalação principal `com.readroid.app`.
- Compilação QA, `apksigner`, alinhamento ZIP, hash SHA-256 e artefato GitHub Actions no workflow `Android APK`. O APK é assinado com chave **debug** de teste, não com certificado de produção.
- Testes estáticos, OTA e instrumentados Android 10/API29 e 15/API35; capturas reais de Home, Explorer e Design para revisão visual.

## Como instalar a prévia QA

1. Abra **GitHub → Actions → Android APK** da branch/PR correspondente ao commit homologado.
2. No final da execução, abra o artefato `NegrecoDroid-P7-v3-preview4-QA` e baixe o ZIP.
3. Extraia `app-qa.apk` e instale no Android. O Android pode exigir autorização de instalação para o aplicativo que abrir o APK.
4. Abra `NegrecoDroid V3 Teste`. Os projetos da instalação principal não são copiados automaticamente.
5. Faça backup de qualquer modificação do seu APK via exportação antes de testar edições.

## Critérios que ainda NÃO foram satisfeitos

- A arte original do mascote e as duas referências PNG **não estão incorporadas como binários ao GitHub**; o SVG e os previews são aproximações, não cópias pixel a pixel.
- As três telas ainda precisam de auditoria de screenshot lado a lado, correção de diferenças, testes de TalkBack/fonte ampliada no físico e aprovação visual explícita.
- O catálogo de **24 temas e 12 layouts completos**, Icon Creator, Logo Studio com edição vetorial real e recursos avançados de decompilação/assinatura não estão implementados integralmente.
- Projeto recente ainda não é histórico persistente multientrada. Build/ameaças sem contadores reais não recebem números fictícios.
- Não ativar publicação OTA, migração da `main` ou merge automático apenas por compilar.

## Rastreamento e evidências

- [#11 — P7 UI 1:1](https://github.com/nego001/ReaDroid-Native/issues/11).
- [#13 — PR da implementação](https://github.com/nego001/ReaDroid-Native/pull/13).
- [Actions: Android APK](https://github.com/nego001/ReaDroid-Native/actions/workflows/android.yml).
- [Actions: P7 brand/screenshots](https://github.com/nego001/ReaDroid-Native/actions/workflows/p7-brand-validation.yml).

**Validação de entrega:** registrar o commit exato e resultado dos quatro workflows antes de declarar que um build está aprovado. Os screenshots das três telas precisam corresponder ao mesmo commit da entrega testada.
