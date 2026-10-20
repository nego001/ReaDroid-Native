# NegrescoDroid V3 · homologação física no Samsung

**Estado:** pendente de execução em aparelho real. Este roteiro documenta os
passos, **não** certifica que eles já ocorreram.

## Antes de começar

1. Use um dispositivo de teste e um APK **de teste** sem dados pessoais. Faça
   backup de quaisquer dados locais relevantes e registre o `versionCode` e
   o certificado da versão instalada.
2. Os APKs `debug` gerados pelo GitHub Actions podem usar certificados que
   não correspondem à instalação anterior. **Não desinstale o aplicativo nem
   limpe dados para contornar `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.** Registre
   bloqueio de assinatura e interrompa esse ensaio, preservando os dados.
3. Não habilite fontes desconhecidas, privilégios extras, root nem OTA apenas
   para rodar os testes. Testar num emulador separado é a alternativa segura.
4. Registre modelo, versão do Android, versão da One UI, idioma, modo de
   navegação (gestos ou três botões), escala de fonte e hash do APK testado.

## Matriz de verificação manual

| Caso | Ação | Critério de aprovação |
| --- | --- | --- |
| TOQUE-01 | Abrir Início, Arquivos, Construir, Segurança, IA e retornar a Início | Todas as cinco abas respondem; nomes e seleção corretos |
| VISUAL-02 | Aumentar texto nas configurações de acessibilidade e repetir navegação | Nenhum botão essencial fica cortado ou coberto pela barra do sistema |
| TALKBACK-03 | Ativar TalkBack e percorrer as cinco abas por gestos de foco | Cada aba é anunciada uma vez, como botão, e a ativa indica estado selecionado |
| TALKBACK-04 | Acionar uma aba com toque duplo e voltar | A seleção altera com feedback coerente; o ícone decorativo não vira parada extra |
| TECLADO-05 | Conectar teclado USB/BT; mover foco com DPAD esquerda/direita | Contorno de foco visível; mudar foco não troca a aba ativa |
| TECLADO-06 | Pressionar ENTER na aba com foco | Seção abre e seu estado selecionado é anunciado |
| TECLADO-07 | Usar TAB/Shift+TAB e Voltar/Escape | Navegação alcança ações da tela; foco não fica preso no rodapé |
| ROTACAO-08 | Abrir APK de teste, trocar seção, girar a tela e retornar | Seção e projeto de teste continuam disponíveis sem corrupção |
| TEMA-09 | Alternar OLED, Claro e Grafite e repetir navegação | Texto, foco e botões permanecem legíveis; projeto não é perdido |
| OTA-10 | Selecionar Estável e Beta e tocar em verificar atualizações | Exibe bloqueio de OTA não configurada; nenhuma instalação ou download inicia |
| SEGURANCA-11 | Conferir arquivo original de teste após ações de análise | Arquivo original não foi alterado ou assinado pelo app |
| EXPLORADOR-12 | Abrir pasta com muitos arquivos, carregar mais, filtrar/pesquisar e girar o aparelho | Pasta, filtro, consulta, página carregada e projeto continuam acessíveis sem alterar o APK original |
| RECUPERACAO-13 | Num APK sintético, salvar cópia criptografada com edição; sair, reabrir o mesmo APK e recuperar após confirmar | Edição volta só após autorização e SHA-256 igual; original intacto |
| RECUPERACAO-14 | Tentar recuperar com outro APK sintético | Bloqueio claro e nenhuma edição do projeto atual substituída |
| RECUPERACAO-15 | Excluir a cópia privada e repetir recuperação | Nenhuma cópia disponível; edições atuais continuam intactas |
| PRIVACIDADE-16 | Abrir Compartilhar plano de alterações e cancelar no aviso | Nenhum aplicativo de compartilhamento é aberto sem consentimento |

Se ocorrer falha, registre **reprodução, resultado esperado, resultado observado,
versão do sistema e foto/captura sem dados pessoais**. Marque cada caso
como `PASSOU`, `FALHOU` ou `BLOQUEADO`. Não marque como aprovado por
inferência baseada no emulador.

## Coleta opcional de diagnóstico pelo computador

Somente com autorização do proprietário do dispositivo e depuração USB já
habilitada, no PowerShell com `adb` instalado:

```powershell
adb devices
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb logcat -d -s AndroidRuntime:E > .\negrescodroid-androidruntime.txt
```

Analise e **remova qualquer dado pessoal, identificador, caminho privado ou
mensagem de outros aplicativos** antes de compartilhar logs. Não envie
`logcat` completo, certificados privados, keystores ou APKs pessoais. O
procedimento não desinstala, instala nem altera arquivos do aplicativo.

## Critérios de encerramento

- [x] Android 10 API 29 e Android 15 API 35: testes automatizados de interface,
  navegação em 320dp e 130% de fonte aprovados nos commits anteriores.
- [x] Nova suíte de teclado/rotação aprovada em API 29 e API 35, 25/25 testes cada (commit `66b7df21`; [Android 10](https://github.com/nego001/ReaDroid-Native/actions/runs/39265428220) e [Android 15](https://github.com/nego001/ReaDroid-Native/actions/runs/39265428681)).
- [ ] Samsung real testado com toque, TalkBack, teclado e rotação.
- [ ] Registro de resultados, modelo, One UI e modo de navegação do Samsung.
- [x] Regressão automatizada com APK sintético, projeto aberto e alteração pendente
  após recriação da Activity: 26/26 no Android 10 e 26/26 no Android 15
  (commit `cafbc97c`). O APK original de teste permaneceu intacto.
- [ ] Verificação manual com um APK de amostra no Samsung físico, sem dados reais.
- [ ] Recuperação de edição após morte do processo Android (não coberta pelo
  mecanismo atual de retenção em memória; não presumir persistência).

**Fora de escopo:** liberar OTA, publicar V3 definitiva, ativar assinatura ou
instalação automática, migrar dados locais sem backup.

### Recuperação: limites antes do ensaio
O salvamento é **manual e opt-in**. Use apenas APKs inventados para o teste,
sem conteúdo privado. Não remova o aplicativo para forçar restauração: isso
apaga o armazenamento privado e pode invalidar sua chave Keystore. Um plano
salvo não substitui o backup do projeto nem garante preservação de edições
feitas após o último salvamento. Na falha criptográfica, interrompa o teste
e não apague cópias sem decisão explícita.

### Verificações automatizadas concluídas
- [x] Android 10: 33/33 testes, commit `5344f58c` ([CI](https://github.com/nego001/ReaDroid-Native/actions/runs/39293953655)).
- [x] Android 15: 33/33 testes, commit `5344f58c` ([CI](https://github.com/nego001/ReaDroid-Native/actions/runs/39293953630)).
- [x] Cofre criptografado testado em emulador: SHA-256 do APK, AES-GCM contra adulteração, diretório/alias isolado, exclusão e limites de tamanho.
- [ ] Recuperação ponta a ponta após interrupção do processo, usando interface do aplicativo e APK fictício no Samsung físico.
- [ ] TalkBack, teclado físico, rotação real e navegação por gestos no Samsung físico.

## APK QA isolado para Samsung (etapa de testes da base, 19/10/2026)

- O pipeline `Android APK` da branch `feature/v3-design-studio` produz um
  **segundo artefato experimental**, `NegrescoDroid-V3-QA-isolated`.
  Ele tem ID Android `com.readroid.app.qa` e rótulo
  **NegrescoDroid V3 Teste**; a versão principal mantém `com.readroid.app`.
- O objetivo é instalar **lado a lado** com o aplicativo atual, sem
  sobrescrever uma versão já instalada com certificado debug diferente e
  sem tocar no sandbox de dados da versão anterior.
- **É um APK de depuração, não uma versão publicada ou de produção.**
  Verifique o nome e o pacote antes de instalar. Use somente APKs fictícios
  para analisar; não abra arquivos pessoais na build QA.
- A assinatura debug de cada execução CI **pode mudar**. Portanto também
  **não é garantida a atualização da própria variante QA** entre execuções.
  Jamais desinstale ou limpe dados para contornar erro de assinatura sem
  antes encerrar os testes, preservar cópias relevantes e escolher fazê-lo.
- O CI confere assinatura, alinhamento, SHA-256 e `applicationId`/rótulo
  do QA, mas **não substitui homologação Samsung**. A instrumentação
  continua cobrindo o app debug principal.
- Nenhum processo altera dados do aplicativo já instalado, publica OTA
  ou solicita permissão adicional.

## Evidência de ensaio físico Samsung (19/10/2026, capturas particulares fornecidas na conversa)
- **PASSOU, observação da interface:** Projeto A sintético foi carregado; usuário inseriu a linha `TESTE NEGRESCODROID V3 12345` em `assets/teste_recuperacao.txt`, e a interface confirmou `Itens no plano: 1`.
- **PASSOU, observação da interface:** após salvamento explícito, o aplicativo mostrou `Cópia protegida` e informou criptografia local. Isto **não** constitui inspeção independente do material armazenado.
- **PASSOU, observação da interface:** ao reabrir o Projeto A e pedir recuperação, a interface informou que a cópia foi autenticada e correspondia ao APK pelo SHA-256; após confirmar, a revisão mostrou `Alterações pendentes (1)`, `assets/teste_recuperacao.txt`, 110 caracteres.
- **PASSOU, recusa esperada:** com Projeto B, o aplicativo exibiu `Recuperação bloqueada`: `Esta cópia pertence a outro APK`. Não foi oferecida substituição do plano.
- **PASSOU, observação da interface às 16:29–16:30 BRT:** após a tentativa bloqueada com Projeto B, o usuário voltou ao Projeto A; apareceu `Plano recuperado` e, na revisão subsequente, `Alterações pendentes (1)`, `assets/teste_recuperacao.txt`, 110 caracteres. Logo a recusa de B não impediu recuperar o checkpoint de A.
- **PENDENTE:** verificar o texto exato no arquivo exportado, comparar com o conteúdo do APK original, registrar confirmação inequívoca de `Forçar parada` e, idealmente, hashes antes/depois para prova independente.
- **PENDENTE:** TalkBack, teclado físico, mudança de rotação, gestos e navegação alternativa no aparelho físico. Não há release final, assinatura de produção nem OTA habilitada.
- Capturas não anexadas ao GitHub. Nenhum dado do usuário além dos resultados técnicos foi copiado.

## Checagem reforçada de integridade de exportação (19/10/2026)
- O APK reconstruído agora é comparado com a cópia original **entrada por entrada**: todas as entradas não editadas devem preservar conteúdo SHA-256, as editadas obedecem ao plano, e o resultado não pode perder/adicionar arquivos fora das remoções esperadas de assinaturas antigas.
- Antes, durante e após exportação, o SHA-256 da cópia de origem é comparado ao hash calculado na importação; o arquivo SAF exportado continua sendo relido integralmente e verificado por SHA-256. O diálogo de detalhes técnicos passa a apresentar hashes completos de entrada e saída.
- Testes sintéticos adicionais cobrem corrupção de entrada não editada, arquivo inesperado e alteração da origem durante o fluxo. **CI não constitui evidência da exportação física Samsung; permanece pendente a captura da exportação, revisão do texto final e verificação independente do arquivo original.**
- Exportação permanece **sem assinatura/sem garantia de instalação**, sem auto-instalação, sem OTA e sem modificação do APK selecionado.

## Regressão ponta a ponta da exportação no emulador (19/10/2026)
- O cenário `tools/android_apk_edit_export_smoke.py` agora confere se o relatório técnico do aplicativo apresenta o SHA-256 da origem e o hash da saída, compara o hash da saída com o arquivo efetivamente recuperado via ADB e exige correspondência SHA-256 de **todas** as entradas não editadas, além de preservar o original e eliminar metadados antigos de assinatura.
- O workflow `v3-apk-edit-export-smoke.yml` passa a iniciar também quando os arquivos centrais do fluxo de reconstrução/exportação forem alterados. Executa somente em emulador descartável com APK de amostra, não acessa arquivos pessoais ou apps existentes no Samsung.
- Ainda é necessária a validação física do fluxo com Projeto A no Samsung, sem limpar dados ou forçar reinstalação de APK QA assinado com chave diferente.

## Conclusão CI do reforço de exportação e início do leitor streaming (19/10/2026)
- **PASSOU no emulador:** workflow [V3 APK edit and export SAF, run 39347377810](https://github.com/nego001/ReaDroid-Native/actions/runs/39347377810), commit `9f172b56`: edição de um recurso de texto sintético → reconstrução sem assinatura → gravação via SAF → comparação do hash exibido no aplicativo com o APK exportado → conferência de **todas** as entradas não editadas e integridade do original.
- **PASSOU:** compilação Android [run 39347377755](https://github.com/nego001/ReaDroid-Native/actions/runs/39347377755). Android 15 [run 39347062107](https://github.com/nego001/ReaDroid-Native/actions/runs/39347062107) e testes de preferências/telas pequenas [run 39347061892](https://github.com/nego001/ReaDroid-Native/actions/runs/39347061892) aprovados no commit `9c2610f2`. Não equivale a teste físico Samsung.
- **Base futura de arquivos grandes:** `StreamingFileProbe` permite leitura **somente leitura por streaming** de arquivos autorizados pelo SAF, SHA-256, limite por bytes e cancelamento por interrupção sem copiar todo o arquivo para cache nem carregar o conteúdo inteiro em RAM. São testes com fixture de cerca de 5 MiB, falha de limite e orçamento `long`; **não** habilita ainda importação de APK acima de 1 GiB, ZIP64, análise de 500 GB ou navegação de pastas multi-GB.
- **PENDENTE no Samsung:** confirmar exportação real do Projeto A, validar texto editado do APK de saída, SHA-256 do original e acessibilidade/rotação; nunca desinstalar a versão QA nem limpar dados para testar, pois cofre e plano local podem ser perdidos.
