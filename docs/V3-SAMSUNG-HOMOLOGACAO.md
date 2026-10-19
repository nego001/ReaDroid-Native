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
- [ ] Avaliação específica de regressão nos arquivos APK usados exclusivamente
  como amostras de teste.

**Fora de escopo:** liberar OTA, publicar V3 definitiva, ativar assinatura ou
instalação automática, migrar dados locais sem backup.
