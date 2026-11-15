# P7.48.1 — Esperar a janela nativa entrar na hierarquia antes de testar Back

Na primeira execução P7.48 [#40159226002](https://github.com/nego001/ReaDroid-Native/actions/runs/40159226002), o Android10 compilou e começou os 45 testes de navegação, mas `androidBackClosesEveryCatalogWithoutCommittingAppearance` falhou na **linha 889**. O relatório JUnit XML no artefato `p7-brand-android-29` confirmou `assertTrue` sem mensagem em `chooser.getWindow().getDecorView().isAttachedToWindow()`.

**Causa do teste:** `opener.performClick()` e `dialog.show()` executaram no próprio `scenario.onActivity`, que verifica a anexação da janela antes de a próxima passagem do Looper/processamento de WindowManager. `isShowing()` pode ser verdadeiro antes de `isAttachedToWindow()`. Esta não foi uma evidência de escolha salva, falha do App ou de que Back fecha incorretamente.

**Ajuste:** manter `assertNotNull` da janela na primeira fase, sincronizar com `waitForIdleSync()`, verificar em **segundo** `scenario.onActivity` a mesma instância de `activeCatalogChooser()`, `isShowing()` e `isAttachedToWindow()`. Só então disparar `KEYCODE_BACK`. Sem excluir asserções, sem dispensar attach real, sem esperar indefinidamente, sem alterar código de produção. Os mesmos 165 testes/API, 14 screenshots/API, 28 cross e Source/OTA continuam obrigatórios.

**Estado:** commit de correção submetido à PR #13, aprovação pendente nova matriz. PR draft, main intacta, visual 1:1 e Galaxy A55/TalkBack físico não aprovados.
