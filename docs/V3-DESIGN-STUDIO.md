# V3 • NegrescoDroid Studio OLED (prévia de desenvolvimento)

## Objetivo
Implementar em UI Android nativa o modelo visual escolhido pelo usuário: base OLED preta,
destaques azuis/neon, cabeçalho com identidade, cartão de projeto, atalhos visuais,
painel de personalização em duas colunas e ações técnicas organizadas.

A referência artística é uma direção de design; o layout é adaptável às dimensões
reais dos celulares. Não é uma captura de tela usada como plano de fundo.

## Implementado
- [x] Nova branch isolada `feature/v3-design-studio`, baseada em `feature/ota-seguro`.
- [x] Marca de cubo, cabeçalho compactado e destaque em `Droid`.
- [x] Cartão do projeto atual com informações reais e botão de seleção de APK.
- [x] Cubo APK neon desenhado via Canvas nativo, sem bitmap, blur ou animações pesadas.
- [x] Quatro atalhos 2×2 com ícones vetoriais, legenda e atalho favorito em primeiro.
- [x] Painel de personalização expansível, com cartões 2×2 preservando callbacks existentes.
- [x] Cor personalizada em hexadecimal #RRGGBB, temas, escala tipográfica e densidade.
- [x] Modos de superfície neon/minimalista e cantos personalizáveis.
- [x] Exportação/importação do novo conjunto de preferências, com validação e compatibilidade com presets antigos de esquema 1.
- [x] Cartões de ações e cabeçalhos explicativos nas abas Construir, Segurança e IA.
- [x] Lista de arquivos com cartões e tipografia de metadados mais legível.
- [x] Paginação do explorador corrigida para realmente renderizar itens além dos 120 primeiros.
- [x] Regressão de paginação com 145 entradas em View Android real.
- [x] Testes Android de exportação/importação visual, com round-trip de 11 preferências e compatibilidade com presets antigos.
- [x] Importador com tipos JSON estritos, sem coerção silenciosa nem caracteres de controle na identidade.
- [x] Testes Android de reconstrução sem assinatura: alteração textual, preservação do original, remoção de assinaturas antigas, rejeição de caminhos inseguros e edições inexistentes.
- [x] Catorze testes instrumentados executados com sucesso no Android API 29, incluindo verificação local SHA-256 do arquivo exportado.
- [x] OTA mantém avisos verdadeiros sobre configuração incompleta e sem instalação automática.
- [x] Navegação inferior com seleção visual em cartões e descrições acessíveis.
- [x] Ajuste de contraste WCAG nos botões, aviso para cor HEX pouco legível.
- [x] Resumo do projeto reduzido; dados técnicos completos permanecem no relatório.
- [x] Troca de tema/rotação retêm APK, relatório e plano textual na mesma sessão.
- [x] Recuperação do arquivo selecionado quando a análise é interrompida pela recriação da Activity.
- [x] Estado aberto/fechado do painel de personalização persistido separadamente.
- [x] Teste no emulador Android (API 29): APK instalado, Início → Arquivos → Segurança → Início, captura de tela gerada.
- [x] Correção da automação: shell POSIX e detecção de crashes tratada pelo script Python.
- [x] Tema Android e cores da barra de status/navegação alinhados à preferência visual.
- [x] Botão Voltar nas outras abas retorna para Início.

## Restrições
- **Não** criar funcionalidades de assinatura APK que o programa ainda não suporta.
- **Não** alterar certificado de APK, chaves, análise de segurança nem as permissões Android.
- Mudanças visuais devem preservar controles, callbacks e resultados técnicos.
- Preferências personalizadas devem continuar funcionando nos temas claro e grafite.
- Nenhuma versão final V3 deve ser publicada automaticamente.
- A arte referência tem brilhos e detalhes decorativos que foram reinterpretados com
  gradientes e desenho vetorial, para evitar consumo excessivo de GPU/CPU.

## OTA e acessibilidade (V3)
- As funções internas OTA exigem configuração compilada, endpoint/chave pública fixados e comprovante da assinatura RSA antes de permitir download.
- No workflow [V3 preferences and narrow screens](https://github.com/nego001/ReaDroid-Native/actions/runs/39195325314), **18/18 testes** passaram e a interface de ambas as opções Estável/Beta exibiu "OTA assinada ainda não configurada" sem oferecer download.
- Os ícones Canvas decorativos foram removidos da navegação assistiva; abas expõem papel de botão e estado selecionado.
- O Android continua sem instalação OTA automática. A ativação, quando autorizada, requer nova auditoria criptográfica, testes de assinatura e consentimento explícito.

## Nova fase de regressões
- 14/14 testes instrumentados aprovados, incluindo verificador de exportação, em https://github.com/nego001/ReaDroid-Native/actions/runs/39192931103
- Edição e exportação ponta a ponta aprovadas: escolher APK de teste, editar `assets/negresco_smoke.txt`, revisar plano, exportar, conferir SHA-256, DEX original e remoção de metadados de assinatura. https://github.com/nego001/ReaDroid-Native/actions/runs/39192735133
- Diálogo compacto e 'Detalhes técnicos' aprovados na execução real: https://github.com/nego001/ReaDroid-Native/actions/runs/39193244238. O APK editado foi validado por SHA-256, e o original permaneceu intacto.
- 10/10 testes instrumentados aprovados no workflow da revisão `abb61da5`: https://github.com/nego001/ReaDroid-Native/actions/runs/39188439031
- 12 testes instrumentados, incluindo validação de prévia de importação, aprovados: https://github.com/nego001/ReaDroid-Native/actions/runs/39190762727
- Exportação/importação ponta a ponta com seletor de arquivos, prévia de alterações e preservação do APK: https://github.com/nego001/ReaDroid-Native/actions/runs/39190807463
- Emulador com 320×640 dp e fonte Android a 130%: navegação pelas cinco abas aprovada após reinstalação do APK no workflow https://github.com/nego001/ReaDroid-Native/actions/runs/39188709664
- Capturas mostraram dica de pesquisa truncada no explorador; o texto da dica e a tipografia foram adaptados para telas estreitas em `fe3b877c`.
- A simulação visual de 320dp reinstala o APK após testes instrumentados. O fluxo agora está comprovadamente aprovado.
- Os testes de reconstrução validam apenas um **ZIP APK sem assinatura**. Não demonstram que o resultado instala no Android.
- O fluxo **completo** de exportação/importação JSON passou pelo DocumentsUI do Android: gerar arquivo em Downloads, conferir JSON, alterar preferências, mostrar prévia validada e restaurar tema/cor mantendo o APK aberto. Ver https://github.com/nego001/ReaDroid-Native/actions/runs/39190807463.

## Validação
- [x] Builds Android intermediários concluídos com sucesso na branch.
- [x] Confirmada compilação Android e verificação de código após `2ebf8208`.
- [x] Examinar a captura real do emulador da primeira execução que abriu e navegou corretamente.
- [x] Workflow de smoke aprovado no commit `2ebf8208` (Android API 29): instalação, abertura, navegação, screenshot e ausência de erros AndroidRuntime.
- [ ] Abrir em celular físico, tocar em todas as opções e conferir rolagem/áreas de toque.
- [x] Seleção SAF de APK real pelo DocumentsUI, análise e exploração de pastas/arquivos em emulador API 29.
- [x] Troca OLED → Claro com um projeto aberto, sem perder os dados do APK.
- [x] Testar exportação e importação pelo seletor de arquivos do Android com um APK real aberto (emulador).
- [x] Edição de texto em APK real de teste, revisão do plano e exportação unsigned pelo DocumentsUI, SHA-256 verificado na gravação, DEX e original preservados.
- [x] Confirmar o novo diálogo compacto de exportação em emulador, incluindo botão 'Detalhes técnicos', verificações SHA-256 e avisos de assinatura.
- [x] Capturas reais dos temas OLED e Claro, com contraste e navegação visivelmente corretos em emulador.
- [x] Teste automatizado com tema Claro, fonte a 130%, modo compacto e retenção do APK aprovado no emulador.
- [x] Testar 320dp com fonte do sistema a 130%: todas as cinco abas visíveis, navegáveis e com alvos de toque adequados.
- [x] Capturas reais do painel inicial e Arquivos em largura de 320dp.
- [ ] Validar telas físicas de diferentes fabricantes.
- [x] Testar importação de presets anteriores e do novo conjunto por instrumentação Android.
- [x] Testar prévia validada, aprovação explícita e aplicação do backup via DocumentsUI com APK aberto.
- [x] Confirmar no emulador que a OTA Estável e Beta está bloqueada sem chave pública/endpoint confiáveis, sem download oferecido.
- [x] Testar o bloqueio interno: sem configuração OTA, verificação e download direto falham antes de usar a rede/cache.
- [x] Testar navegação acessível com botões nomeados, aba selecionada e ícones decorativos sem anúncios duplicados.
- [ ] Concluir validação manual de TalkBack e teclado físico em dispositivo real; testes automatizados de semântica de navegação aprovados.

## Evidências verificáveis
- Primeiro teste de APK e tema aprovado: https://github.com/nego001/ReaDroid-Native/actions/runs/39183969729
- Builds Android e verificações de código aprovados até `e7830d7c`.
- Teste estendido de APK, OLED → Claro, fontes a 130% e modo compacto aprovado: https://github.com/nego001/ReaDroid-Native/actions/runs/39184741134
- Build Android e Source checks aprovados no commit `bfdc8717`.

Este trabalho fica numa branch de desenvolvimento, separado do lançamento
`v3.0.0-preview.1` e de futuras versões definitivas.

## Endurecimento do parser e download OTA direto (19/10/2026)
- O parser não aceita versões fracionárias, números como strings nem campos textuais convertidos implicitamente pelo `org.json`.
- URLs de APK em HTTPS com portas não padrão são rejeitadas, mantendo a mesma política do downloader.
- O downloader recusa diretamente metadados sem assinatura verificada antes de criar arquivo temporário ou iniciar rede, mesmo se invocado sem o pipeline.
- Testes Android dedicados cobrem falsificação de JSON, portas proibidas e a chamada direta ao downloader sem assinatura.
- Mudanças em qualquer `Ota*.java` agora acionam a suíte de emulador V3 na branch de desenvolvimento.
- Permanece pendente o teste manual de TalkBack e de teclado físico em Samsung; nenhuma OTA é ativada ou instalada automaticamente.

## Android 15: falha real de inicialização e compatibilidade edge-to-edge (19/10/2026)
- A primeira rodada API 35 falhou ao iniciar `MainActivity` com `NullPointerException` no acesso antecipado a `Window.getInsetsController()`. Evidência: https://github.com/nego001/ReaDroid-Native/actions/runs/39196400145.
- Correção: aplicar a aparência das barras somente após anexar a interface, lendo o controlador diretamente do decor view de forma anulável.
- No Android 15 (targetSdk 35), reservar os insets de status, navegação e recortes da tela no contêiner raiz, incluindo navegação por gestos ou três botões.
- Portão obrigatório: reexecutar a suíte de instrumentação e o smoke de navegação no emulador API 35, verificando que a interface permanece visível e não ocorre crash.
- **Não considerar homologado até que a nova execução de CI seja aprovada.** Testes de TalkBack em Samsung físico ainda pendentes.

## Android 15: regressão real e falso negativo por Launcher (19/10/2026)
- A execução https://github.com/nego001/ReaDroid-Native/actions/runs/39196927845 passou **22/22 testes instrumentados**, incluindo segurança OTA, acessibilidade e reconstrução; o crash inicial de `WindowInsetsController` não se repetiu.
- A automação visual falhou porque o **Pixel Launcher do emulador** exibiu `Pixel Launcher isn't responding` por cima do NegrescoDroid. Evidência: `v3-studio-android-hierarchy.xml` e captura de tela do artifact `12162009636`. O relatório `v3-studio-android-runtime.txt` estava vazio.
- O smoke agora reconhece **apenas** o alerta com título exato e pacote `android`, clica uma única vez em `android:id/aerr_close`, relê a hierarquia e exige a seleção correta da aba. Alertas do NegrescoDroid ou outras janelas **não** são dispensados silenciosamente.
- Testes Python isolados verificam o caso de recuperação, a ausência de intervenção em alertas distintos e a rejeição de um ANR do próprio app.
- A aprovação do gate API 35 depende de **nova execução completa**, não apenas dos 22 testes anteriores. Teste físico Samsung/TalkBack segue pendente.

## Resultado da homologação automatizada Android 15 (19/10/2026)
- **Aprovado:** workflow [V3 Android 15 compatibility #39259425407](https://github.com/nego001/ReaDroid-Native/actions/runs/39259425407), commit `4ac4d1f4`.
- **22/22 testes instrumentados Android 15** aprovados, sem testes ignorados.
- **6/6 testes Python** da recuperação restrita do Pixel Launcher aprovados.
- **Smoke real no emulador:** Início → Arquivos → Segurança → Início, sem crash detectado do NegrescoDroid.
- Artefato de prova: `NegrescoDroid-V3-Android15-Validation` (`12189138331`). Hierarquia final contém as cinco abas, sem alerta do launcher; captura final foi inspecionada e mostra navegação e barras do Android sem sobreposição.
- `v3-studio-android-runtime.txt` vazio (sem erros AndroidRuntime registrados no intervalo testado). A compilação Android e a checagem de código do mesmo commit também passaram.
- Limites: teste visual somente com o emulador Google APIs API 35, perfil Pixel 3a, usando a navegação configurada pelo sistema. **Não equivale a homologação física em Samsung**, nem a ensaio de TalkBack, teclado, gestos/3 botões em modelos variados ou OTA real.
- OTA continua desativada; V3 definitiva **não publicada**.

## Regressão de tela estreita no Android 15: APROVADA (19/10/2026)
- Commit do teste `ca559c8f`; execução [#39260458089](https://github.com/nego001/ReaDroid-Native/actions/runs/39260458089) **aprovada**.
- O Android 15 API 35 passou a suíte instrumentada (22 testes), os seis testes Python do recuperador de Launcher e o smoke normal sem crash detectado.
- Em `wm size 320x640`, `wm density 160`, `font_scale 1.3`, as cinco abas ficaram visíveis e funcionais. Smoke confirmou retorno ao Início.
- Capturas `v3-studio-narrow-home.png`, `v3-studio-narrow-files.png`, `v3-studio-narrow-return.png` e `v3-studio-narrow-final.png` estão no artefato de CI `NegrescoDroid-V3-Android15-Validation` (ID `12190841052`). A captura inicial de 320dp foi inspecionada: rodapé e navegação do sistema não se sobrepõem visualmente.
- Log `v3-studio-narrow-runtime.txt` vazio no período. Builds Android e verificações de código do commit do teste aprovados; a suíte Android 10 `#39260457912` também passou.
- **Escopo:** teste automatizado apenas em emuladores; homologação física Samsung, TalkBack e teclado físico seguem pendentes. O app não instala atualizações OTA nem possui release V3 definitivo.

## Teclado físico, foco e recriação da Activity (19/10/2026)
- Cada uma das cinco abas recebe um ID único; DPAD esquerda/direita percorre as abas vizinhas sem forçar a seleção. TAB e Shift+TAB permanecem sob navegação padrão para não prender o usuário no rodapé.
- O foco de teclado passa a ter contorno de 2 dp, independentemente da seção ativa. O estado `selecionada` continua anunciado separadamente.
- Novos testes instrumentados validam ordem do DPAD, ativação com ENTER (incluindo papel e estado acessível) e manutenção da seção selecionada após recriação da Activity.
- Os testes rodam em emuladores API 29 e API 35. O teste manual com teclado Bluetooth/USB e TalkBack no Samsung **continua pendente**; nenhuma homologação física foi inferida.
- OTA assinada continua sem endpoint/chave de produção, sem instalação automática e sem publicação da V3 definitiva.

## Resultado da regressão de teclado/rotação (19/10/2026)
- O commit `66b7df21` passou **25/25 testes instrumentados no Android 10 (API 29)**: https://github.com/nego001/ReaDroid-Native/actions/runs/39265428220.
- O mesmo commit passou **25/25 testes instrumentados no Android 15 (API 35)**: https://github.com/nego001/ReaDroid-Native/actions/runs/39265428681.
- Novo teste `KeyboardAndRotationInstrumentedTest`: foco horizontal DPAD, ENTER selecionando corretamente e recriação preservando a aba ativa. O teste agora envia evento de teclado antes de pedir foco; o modo touch do emulador rejeitava foco de botão, como previsto pela API Android.
- Regressão de UI: cinco abas em `320x640` e fonte 130% aprovadas nos dois emuladores. Os avisos de OTA Estável/Beta permanecem bloqueados nos testes API 29.
- `Android APK` e `Source checks` também aprovados para `66b7df21`. Testes de foco **não** substituem TalkBack em aparelho físico; ainda não há aprovação de Samsung, teclado Bluetooth, navegação por gestos em diferentes modelos ou instalação OTA.
- Procedimento seguro de testes físicos documentado em [V3-SAMSUNG-HOMOLOGACAO.md](V3-SAMSUNG-HOMOLOGACAO.md).

## Preservação de projeto com edição pendente: testes aprovados (19/10/2026)
- Commit `cafbc97c`: `ProjectRecreationInstrumentedTest` exercita a recriação da `MainActivity` com um **APK ZIP sintético sem assinatura**, relatório carregado, seção Arquivos ativa e edição textual pendente.
- **Android 10 API 29: 26/26 testes**, nenhum ignorado ou falho. [Execução #39266803432](https://github.com/nego001/ReaDroid-Native/actions/runs/39266803432).
- **Android 15 API 35: 26/26 testes**, nenhum ignorado ou falho. [Execução #39266803823](https://github.com/nego001/ReaDroid-Native/actions/runs/39266803823).
- O teste confirma que o arquivo em cache, o relatório, a edição pendente e a aba ativa sobrevivem à recriação; os bytes do APK original de teste permanecem idênticos.
- Também foram aprovados os smoke tests de navegação em 320dp com fonte 130%; os canais de OTA Estável/Beta permanecem bloqueados no emulador API 29.
- **Limite explícito:** recriação de Activity não representa morte do processo nem recuperação de dados após desinstalação. Projetos e alterações continuam sujeitos às limitações do armazenamento temporário; testar dados reais exige backup seguro e homologação física.

## Clareza sobre alterações não persistidas (19/10/2026)
- O editor de texto e a confirmação de edição mostram que **o plano é mantido apenas em memória**. A recriação da Activity retém o plano, mas morte do processo Android, encerramento da sessão ou perda do cache **podem descartar alterações pendentes**.
- O aplicativo aconselha exportar o resultado da edição quando necessário, sem sugerir que o ZIP unsigned exportado pode ser instalado no Android.
- Nenhum salvamento automático, banco de dados, migração de dados, chave privada ou acesso OTA foi criado nesta etapa.

## Recuperação do estado do explorador (19/10/2026)
- O estado de navegação do explorador (pasta, filtro, texto da busca e limite de paginação) passa a integrar a retenção **temporária em memória** da Activity junto do APK, relatório e plano de edição.
- Ao restaurar, a pasta só é aceita se ainda corresponder a arquivos do mesmo projeto, e filtros e valores de paginação são validados antes de renderizar. Ao carregar um APK diferente, a navegação continua sendo reiniciada.
- Teste instrumentado adicional usa um ZIP sintético, seleciona Arquivos, aplica pasta/filtro/busca e exige preservação após recriação da tela; o arquivo original permanece intacto.
- **Limite:** não há persistência após morte do processo, desinstalação, limpeza de cache ou perda de permissões. O comportamento em Samsung físico continua pendente.

## Explorador: restauração de pasta, pesquisa, filtro e paginação (19/10/2026)
- `479de2d6`: o `WorkspaceState` passa a carregar `ExplorerView.BrowseState` (pasta, filtro, busca, limite de página), em memória, junto do APK, relatório e edições.
- A restauração exige uma pasta ainda presente no projeto e categoria conhecida, além de limitar a busca e a paginação. Abrir outro APK continua zerando a navegação do explorador.
- `e11a01d9`: novos testes instrumentados incluem busca e filtro restaurados, além de uma pasta com 145 entradas reais em ZIP sintético, carregamento da página dois e comparação dos bytes originais após recriação da Activity.
- Uma execução anterior revelou instabilidade intermitente no teste de foco por teclado: `#39271760568` falhou antes do DPAD sair do modo toque; a execução `#39272076781` aprovou o mesmo cenário, confirmando natureza intermitente. Não era falha detectada na restauração do explorador.
- `afe426c4`: o teste de teclado agora aguarda a UI e repete até cinco eventos de DPAD, exigindo que a aba realmente saia do modo de toque, em vez de ignorar a validação.
- **Android 10 API 29: 28/28 testes instrumentados aprovados**, sem ignorados, com UI 320dp/fonte 130% e OTA bloqueada: https://github.com/nego001/ReaDroid-Native/actions/runs/39272579774.
- **Android 15 API 35: 28/28 testes instrumentados aprovados**, sem ignorados, com smoke de navegação e UI 320dp/fonte 130%: https://github.com/nego001/ReaDroid-Native/actions/runs/39272579450.
- `Source checks` e `Android APK` também aprovados no commit `afe426c4`.
- Escopo: regressão de recriação da Activity em emuladores. **Não** demonstra sobrevivência após término do processo Android, nem uso de TalkBack, navegação por gestos ou teclado USB/BT em Samsung físico. OTA e release V3 definitivo permanecem desabilitados.

## Cópia de recuperação local sob consentimento (19/10/2026)
- `RecoveryVault` oferece **somente sob ação explícita** uma cópia do plano de alterações pendentes (sem bytes do APK), criptografada com AES-256-GCM e chave criada pelo Android Keystore. O arquivo fica no diretório privado de arquivos do aplicativo e **não** é enviado à nuvem; `allowBackup=false` continua.
- Na aba Construir: **Salvar cópia de recuperação criptografada**, **Recuperar plano salvo neste aparelho** e **Excluir cópia de recuperação local**. Salvar exige um APK aberto com ao menos uma alteração, substitui apenas a cópia anterior (slot único) e grava arquivo temporário com sincronização antes de substituição atômica.
- Restaurar exige reabrir o **mesmo APK com SHA-256 correspondente**. Criptografia autenticada impede adulterações silenciosas; formato, quantidade, tipo e caminhos das alterações são revalidados. O usuário confirma antes de **substituir** o plano pendente atual. O APK original nunca é gravado pela recuperação.
- Os limites são 100 alterações, 128 KiB por texto e 512 KiB totais no JSON. A cópia não contém chave nem certificado; chaves da Keystore não são exportadas.
- Os testes `RecoveryVaultInstrumentedTest` usam diretórios e aliases de chave **exclusivos por teste**: round-trip após nova instância, rejeição de outro APK, detecção de ciphertext adulterado, rejeição de caminho inválido/plano grande sem sobrescrever backup válido e exclusão segura do arquivo.
- `Compartilhar plano de alterações` agora exige aviso explícito, pois esse fluxo envia **JSON legível** ao aplicativo escolhido. Não é o mesmo que a cópia criptografada.
- Limites: salvar não é automático. Alterações realizadas depois do último salvamento não entram na cópia até uma nova confirmação; sem a chave Android local, os dados não são recuperáveis. Desinstalar, limpar dados, trocar dispositivo ou invalidar a Keystore pode impedir recuperação. O APK de origem deve estar disponível para seleção novamente.
- **Pendente**: homologação real do fluxo no Samsung e validação de retomada manual após encerramento forçado do processo. CI em emulador não equivale à homologação física. A OTA permanece bloqueada e a V3 não foi publicada.

## Cópia criptografada: regressão automatizada APROVADA (19/10/2026)
- Commit de código final `5344f58c`: **Android 10 API 29, 33/33 testes instrumentados aprovados**, nenhum ignorado ou falho: https://github.com/nego001/ReaDroid-Native/actions/runs/39293953655.
- O mesmo commit: **Android 15 API 35, 33/33 testes instrumentados aprovados**, nenhum ignorado ou falho: https://github.com/nego001/ReaDroid-Native/actions/runs/39293953630.
- Android 10: navegação das cinco abas com 320 dp e 130% de texto aprovada; botões OTA Estável/Beta permanecem bloqueados na ausência de configuração.
- Android 15: smoke de navegação e tela estreita aprovados sem crash do aplicativo detectado.
- Os cinco novos testes `RecoveryVaultInstrumentedTest` verificaram restauração por nova instância, rejeição de APK diferente, alteração de ciphertext detectada pela autenticação GCM, rejeição de planos inválidos/grandes preservando a cópia anterior e exclusão da cópia; diretório e alias da Keystore de teste são isolados do usuário.
- O teste de teclado original apresentou falha intermitente de entrega global do ENTER ao emulador em uma execução anterior. `5344f58c` passou a encaminhar eventos `KeyEvent` ao componente nativo em foco para verificar sua ativação de modo determinístico; **a rota de hardware/teclado Bluetooth real permanece pendente**.
- Build Android e `Source checks` do commit `5344f58c` aprovados. O armazenamento de recuperação depende do consentimento explícito; **não foi implementado salvamento automático**, compartilhamento em nuvem, instalação por OTA nem publicação final.
- Limites de homologação: o teste de nova instância não equivale a matar o processo com um projeto real e restaurar pelo fluxo completo da interface. Confirmar manualmente no Samsung usando apenas APK sintético, sem dados privados, antes de considerar a V3 pronta para uso real.

## Fase futura de UX registrada, sem execução (19/10/2026)
- Solicitação observada no Samsung: melhorar os dois diálogos cinza de **Planejar alteração** e **Alteração registrada / Itens no plano**.
- Planejado para **depois da base**, no issue [#1](https://github.com/nego001/ReaDroid-Native/issues/1); esta alteração não redesenha telas.
- Correção independente da base: o editor distingue `ADDED`, `UPDATED`, `REMOVED` e `UNCHANGED`, sem declarar sucesso quando o texto permaneceu igual ao original e o plano está vazio. A base funcional e os testes têm prioridade.
- O APK que já estiver instalado no Samsung não incorpora a correção até a instalação de um build novo e compatível, sem desinstalar/apagar dados.

## Base de testes: variante instalável lado a lado (19/10/2026)
- Criado build type `qa` com `applicationId` `com.readroid.app.qa`,
  isolado do aplicativo principal `com.readroid.app`.
- O manifesto específico `src/qa` identifica a variante como
  **NegrescoDroid V3 Teste**, sem modificar o rótulo da versão principal.
- GitHub Actions compila e verifica o APK QA separadamente, incluindo
  assinatura debug, ZIP alignment, SHA-256, pacote e rótulo; publica artefato
  com nome inequívoco.
- Limites de teste: o certificado debug pode mudar entre execuções, logo
  atualizar a própria variante QA não é garantido. Isso **não** libera OTA,
  não instala software e não torna a variante uma release definitiva.

## Diagnóstico estrutural offline por tipo de APK (19/10/2026)
- Primeira entrega da issue [#2](https://github.com/nego001/ReaDroid-Native/issues/2): após selecionar e analisar um APK, o resumo inclui **PERFIL** e aparece o botão **Ferramentas recomendadas para este APK** na tela Início.
- `ApkIntelligence` inspeciona apenas nomes de arquivos já indexados, sem rede nem execução do APK. Reconhece indícios de Unity, Unreal Engine, Flutter, React Native, Android/ZIP ou **sinais mistos**; exibe o porquê da detecção e nunca afirma compatibilidade garantida.
- A lista separa claramente ferramentas já utilizáveis (metadados, manifesto, busca, SHA-256, comparação, editor UTF-8 pequeno e exportação unsigned) daquelas que ainda não existem (DEX, assets binários Unity/Unreal, splits/APKS/XAPK, rebuild instalável).
- Casos sintéticos de teste: cada perfil, ambiguidade, indícios incompletos e limitação explícita. A interface de editor antiga **não foi alterada**.
- Limite atual de importação continua 1 GiB; abertura multi-GB, indexação escalável e edição de formatos especializados dependem das próximas etapas de infraestrutura, memória/armazenamento e ensaios físicos.

## Importação de arquivos maiores: pré-inspeção segura (19/10/2026)
- `ApkImportPreflight` confere o tamanho declarado pelo provedor SAF (quando existente) e o espaço realmente disponível no cache privado, reservando 64 MiB antes da cópia.
- O importador contabiliza bytes **de fato lidos** (não confia apenas em `OpenableColumns.SIZE`) e reavalia espaço livre a cada 32 MiB, encerrando com limpeza do temporário se exceder 1 GiB ou faltar armazenamento.
- Fluxo sem novo privilégio Android, sem upload, sem execução de código e sem alterar o APK de origem.
- APK acima de 1 GiB **permanece bloqueado** explicitamente até existir infraestrutura sob demanda para ZIP64/metadados paginados, mais testes físicos de RAM, armazenamento e integridade.
- Quatro testes instrumentados emulam tamanho declarado acima do limite, reserva insuficiente, tamanho desconhecido e checagem periódica de disco.

## Roadmap pós-Android: Windows, Linux e REA (19/10/2026)
- O objetivo foi refinado na [issue #3](https://github.com/nego001/ReaDroid-Native/issues/3): **Android é o produto atual focado em APK**; **Windows e Linux serão produtos desktop orientados principalmente à análise e edição controlada de executáveis .exe/PE**. No Linux, também haverá foco em binários nativos **ELF** e bibliotecas `.so`. Analisar PE no Linux offline não significa executar EXE/Wine.
- Base de engenharia reversa proposta: [REA oficial, morluto/rea](https://github.com/morluto/rea), com integração **CLI/MCP** e provedores como Ghidra/Hopper/IDA onde houver suporte real, além de trilhas específicas para `.NET` e Electron. O REA fornece evidências/analises, **não é editor ou clonador universal de EXE**, e o suporte Ghidra Windows é experimental.
- Arquitetura: núcleo compartilhável de análise/patch/diff e adaptadores específicos para Android, Windows e Linux, sem tentar transportar `AndroidKeyStore`, `PackageManager`, SAF ou permissões Android para o desktop.
- Primeiro objetivo desktop: inventário e detecção PE/ELF, arquitetura, seções, imports/exports, assinaturas e SHA-256; análise estática de funções/assembly/pseudocódigo quando provedor disponível. Em seguida, edição reversível de recursos suportados, exportação em **novo arquivo**, backup, comparação, testes e validação; alterar um EXE pode invalidar sua assinatura digital.
- REA está sob licença MIT para o código próprio, enquanto Ghidra/Hopper/IDA e outras dependências têm condições independentes; não embutir/redistribuir componentes sem verificação de licenças, nem baixar/executar binários não confiáveis automaticamente. Dinâmica somente mediante consentimento e isolamento.
- Escolha de UI/empacotamento desktop dependerá de prova de conceito Windows + Linux, com fixtures PE e ELF, medição de memória/desempenho, integração local e modelo de confiança.
- **Estado: somente planejamento pós-Android**, sem versão Windows/Linux ou integração REA produzida. A base Android, APKs grandes (issue #2) e homologação física continuam prioritários; redesenho Android separado (issue #1).

## Explorador multi-GB e projetos sincronizados entre plataformas (19/10/2026)
- Requisitos de produto, segurança, offline-first e benchmarks organizados no documento [MULTI_GB_EXPLORER_AND_SYNC.md](MULTI_GB_EXPLORER_AND_SYNC.md).
- [Issue #2](https://github.com/nego001/ReaDroid-Native/issues/2): explorador de arquivos/pastas semelhante a um gerenciador completo, indexação paginada e processamento multi-GB por streaming; o limite atual de APK 1 GiB **não foi removido**.
- [Issue #4](https://github.com/nego001/ReaDroid-Native/issues/4): sincronizar **projetos que o usuário decidir adicionar ao workspace NegrescoDroid**, com modo offline por padrão e, futuramente, E2EE e histórico de revisões. Arquivos de origem enormes exigirão escolha explícita para upload.
- [Issue #3](https://github.com/nego001/ReaDroid-Native/issues/3): compatibilidade de projetos com Windows/Linux e ferramentas EXE/ELF + REA, **após** Android.
- Apenas documentação/roadmap: **nenhum serviço de nuvem está configurado, nenhum arquivo foi enviado, não há sincronização automática e o explorador multi-GB ainda não está pronto**.

## CTA — Controle de Análise, IA coordenadora multiplataforma (19/10/2026)
- Requisito registrado em [issue #5](https://github.com/nego001/ReaDroid-Native/issues/5):
  o CTA será a **única IA compartilhada entre Android, Windows e Linux**,
  distribuindo trabalho para agentes IA **exclusivos de cada plataforma**.
- A liberação de operações será **adaptativa por aparelho, provedor, formato,
  tamanho, espaço, RAM, motores homologados e consentimento**. Para arquivos
  de 1 a 500 GB ou mais: separar inspeção de metadados, streaming, indexação
  com seek e edição/reconstrução; 500 GB não é promessa de suporte no Android.
- Primeira política determinística e testes em
  `AnalysisCapacityPolicy` não habilitam análise real de 500 GB nem
  implementam o CTA; limites atuais permanecem intactos.
- Especificação completa no documento
  [MULTI_GB_EXPLORER_AND_SYNC.md](MULTI_GB_EXPLORER_AND_SYNC.md).

## Plano mestre de 28 módulos (19/10/2026)

- O usuário aprovou **todas as 12 propostas iniciais** e pediu mais funcionalidades. As **28 capacidades previstas** estão detalhadas no [plano mestre #9](https://github.com/nego001/ReaDroid-Native/issues/9), com IDs F01–F28, fases, dependências, segurança e critérios de aceite.
- Eixos principais: **Deep Explorer** multi-GB, **Adaptive Engine**, Format Radar, Hex Lab, Smart Editor e Build Factory; **Time Machine** e Security Command; **Mission Control** com General Supremo → CTA → CTO → generais dos sistemas e agentes especializados, todos com permissões limitadas; laboratório de testes, compatibilidade, diagnósticos e busca; sincronização E2EE opcional e versões Windows/Linux com REA após homologação Android.
- **Próxima entrega técnica**: infraestrutura Android de explorador indexado/virtualizado por partes, sem carregar arquivos imensos ou listagens completas na RAM. Não elevar limite atual de importação de 1 GiB sem streaming/seek/ZIP64 verificados em teste real. No Android, uma análise de 500 GB ou multi-TB só é possível em operações/provedores com capacidade provada.
- Cada capacidade terá estados visíveis **Planejado → Experimental → Testado → Disponível**, ou **Bloqueado** se não houver suporte seguro. Não anunciar 28 módulos como implementados.
- A UI futura (issue #1) permanece após a estabilização funcional. OTA continua desativada. Nenhum APK/EXE é executado ou sincronizado automaticamente; ações de maior risco dependem de autorização.

## Homologação total das 28 funções no encerramento (19/10/2026)
- Requisito do usuário registrado na [issue #10](https://github.com/nego001/ReaDroid-Native/issues/10) e vinculado ao [plano mestre #9](https://github.com/nego001/ReaDroid-Native/issues/9): implementar F01–F28 progressivamente e **ao final** entregar script/suíte de validação completa com registro de execução e evidências.
- Runner futuro: manifesto de casos F01–F28 por SO e versões; CLI/CI e testes de dispositivo, quando existirem; resultados verificáveis `PASS`, `FAIL`, `SKIP_UNSUPPORTED`, `NOT_IMPLEMENTED`, `BLOCKED_MISSING_CONSENT`, `MANUAL_REQUIRED`.
- Artefatos previstos: `results.json` + `summary.md` + `report.html` + JUnit XML quando aplicável. Relatar versão/commit, duração, ambiente, métricas, hashes e causas de erro; nunca registrar senhas/chaves/dados privados em claro.
- Homologação final depende de **testes reais Android/Samsung**, integridade e exportação, e posteriormente builds desktop, sem tratar testes de política com arquivos esparsos como prova de processamento real de 500 GB.
- **Script final ainda não implementado.** Testes automatizados existentes continuam desde agora a cada fase; o script final agrega e audita a cobertura completa, não substitui testes incrementais.

## Índice de arquivos ZIP em disco: P1 experimental (19/10/2026)

- Novo `ApkDiskIndex` cria um **índice SQLite em arquivo privado**, sem produzir um `JSONArray` de todos os caminhos. Insere metadados durante a enumeração, cria pastas implícitas, separa rótulos, caminho, categoria, tamanho e origem explícita; consultas por pasta, busca ou categoria retornam **no máximo 120 itens**, com contagem de resultados.
- Impõe limite de entradas 150 mil, tamanho de cada entrada 1 GiB e total descompactado 2 GiB, rejeita traversal, profundidade excessiva, nomes enormes e índice existente, aplica cota SQLite de ~128 MiB e apaga o banco incompleto se houver falha/cancelamento. Metadados de tamanho/data da origem evitam reutilizar índices obviamente obsoletos, mas não substituem hash de integridade.
- Testes instrumentados com ZIPs sintéticos verificam **301 arquivos em três páginas**, busca por nome, pastas implícitas/explicitas, rejeição de traversal, paginação excessiva, arquivo modificado e rollback de banco incompleto.
- **Ainda não conectado à interface atual**, que continua usando o explorador legado em memória: é uma etapa isolada de preparação. Não certifica ZIP64 multi-GB, não altera importação 1 GiB nem possibilita análise de 500 GB. Próxima fase: conectar o índice ao fluxo de importação, ao `ExplorerView` e gerenciar ciclo de vida/limpeza com testes de regressão.

## Integração inicial do explorador SQLite na interface (19/10/2026)

- Após CI verde do commit `80abad4e` em Android 10 e 15, o app passa a **tentar criar índice SQLite privado a partir de 200 entradas** e oferece paginação visual de 120 itens por vez, navegação de pastas e busca. Botões anterior/próxima substituem a ampliação de centenas de cartões no modo indexado. Os filtros especializados ainda usam o modo clássico para preservar os estados Editáveis/Alterados.
- A Activity preserva a referência ao índice em mudanças de orientação, descarta o índice ao trocar de projeto e limpa no encerramento sem mudança de configuração. Se a indexação falhar, volta ao catálogo legado. Teste instrumentado novo cobre 301 entradas, página 2 e 3, busca e plano de edição.
- **Limitação conhecida da etapa:** o JSON integral ainda é produzido pela análise e retido para relatório/assistente. Esta implementação não remove totalmente o consumo linear de RAM da importação e **não** eleva o limite de APK 1 GiB. Requer novos testes Android, SAF, rotação e regressão antes de homologar no Samsung.
