# NegrecoDroid P7 — Preview 12: Explorador fiel à estrutura aprovada

**Data:** 20/10/2026 (Brasil)  
**Versão QA:** `3.0.0-preview.12-p7-qa` (`versionCode=12`)  
**Pacote paralelo:** `com.readroid.app.qa`  
**Branch:** `feature/p7-negrecodroid-visual-foundation`  
**PR:** [#13](https://github.com/nego001/ReaDroid-Native/pull/13)  
**Referência obrigatória:** [P7 #11](https://github.com/nego001/ReaDroid-Native/issues/11)

## Base verificada: Preview 11

A Preview 11 passou na compilação, verificações de código, OTA e testes instrumentados Android 10/API29 e 15/API35, inclusive testes do mascote e da navegação. Capturas reais mostram as diferenças que motivaram esta rodada: Explorer antigo com título genérico, cartão vertical grande, buscador alto, filtros avançados numa linha própria e arquivos em cartões excessivamente arredondados.

## Mudanças efetivamente implementadas

- [x] `P7ExplorerChrome`: **seta nativa de voltar** no topo, ao lado de `Explorador de Arquivos`. Se o usuário está dentro de uma pasta, volta um nível; na raiz, retorna à Home. A navegação é passada pela Activity, não simulada.
- [x] **Menu ⋮** no canto direito, com acesso ao seletor real SAF para abrir outro APK e opção de voltar ao início.
- [x] **Cartão horizontal de APK** com ícone de arquivo, nome e resumo reais do APK (ou mensagem de estado vazio) à esquerda e chip de `Plano de edição` à direita. A cor e o formato são de componentes Android, sem screenshot estático.
- [x] Contador de edições **clicável**, ligado ao método `MainActivity.reviewEditPlan`, inclusive quando não há edições.
- [x] Breadcrumb continua acima da busca, com segmentos clicáveis; margens compactadas.
- [x] `ExplorerView`: chips **Todos / Smali / Recursos / Imagens / XML** e opção `Filtros avançados` na **mesma linha**, com acesso aos filtros técnicos adicionais. Busca compacta.
- [x] Linhas dos arquivos mais densas, com ícones e separadores discretos, mantendo paginação SQLite, preview, inspeção técnica e edição restrita aos formatos realmente permitidos.
- [x] `P7ExplorerChromeInstrumentedTest`: verifica controles nativos de voltar, menu, filtro e plano; confirma callbacks reais; mantém todos os cenários de filtro XML e navegação.
- [x] `tools/p7_explorer_smoke.py`: exige os cinco chips e os controles de cabeçalho no emulador, além de tirar screenshot.
- [x] Todas as alterações na branch de desenvolvimento; `main` intocada e sem OTA de distribuição.

## O que ainda falta para 1:1

- A imagem da referência contém um APK real aberto com muitas linhas, enquanto a captura padrão dos testes usa legitimamente a sessão **sem APK**. Não inventar projetos/arquivos ou mostrar um ZIP fictício só para imitar uma campanha publicitária.
- Para validação 1:1 com a lista preenchida, o teste de screenshot precisa abrir um **fixture APK de teste controlado**, claramente identificado como tal, ou o proprietário deve importar seu próprio APK no aparelho.
- Correspondência final de tipografia, densidade, ícones de arquivos individuais, ícones de apps, sombras e margens ainda depende de screenshots comparativos no tamanho de tela-alvo.
- A matriz Android 10/15 do commit final e o teste no Galaxy A55 precisam de confirmação. Os recursos complexos de edição/decompilação e criação de logos/ícones continuam em desenvolvimento.

**Não é uma versão de produção. Não fazer merge automático nem afirmar fidelidade total 1:1 antes do aceite do usuário.**
