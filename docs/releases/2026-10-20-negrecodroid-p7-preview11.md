# NegrecoDroid P7 — Preview 11 (acabamento visual e projetos)

**Data:** 20/10/2026  
**Versão Android:** `3.0.0-preview.11-p7` / `versionCode=11`  
**Pacote QA isolado:** `com.readroid.app.qa`  
**Revisão de implementação:** [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13) · [Referência P7 #11](https://github.com/nego001/ReaDroid-Native/issues/11)

## Resultados comprovados antes desta revisão

A [Preview 10](https://github.com/nego001/ReaDroid-Native/tree/preview/p7-v3.0.0-preview10) passou em `Android APK`, `Source checks`, `OTA manifest validation` e na matriz de emuladores Android 10/API29 e 15/API35. A inspeção de `p7-brand-android-35.png` mostrou que o personagem já aparece à frente do cartão, mas o recorte fotográfico apresentava quatro bordas retangulares contra o fundo OLED. Este é o defeito visual que motivou a Preview 11.

## Implementação Preview 11

- [x] O **mascote original**, extraído da arte aprovada, continua incorporado offline ao APK. `P7MascotView` agora aplica dois `DST_IN` com gradientes de transparência horizontal e vertical para integrar as bordas ao fundo preto. Não é outra imagem gerada nem substitui a Home por um screenshot.
- [x] A região com engrenagem duplicada continua recortada; o botão real de configurações permanece utilizável.
- [x] Teste instrumentado `P7MascotArtworkInstrumentedTest` adicional desenha o componente em um `Canvas` transparente e compara o conteúdo central com a transparência das bordas. Evita regressão para uma imagem retangular colada sobre a Home.
- [x] **Projetos recentes:** cada linha autorizada recebeu botão contextual `⋮` acessível, como na imagem de referência.
- [x] O menu por projeto oferece duas ações reais: **Abrir projeto** (reanalisa o arquivo autorizado) e **Remover do histórico** (confirma, apaga só os metadados recentes e a miniatura privada, sem deletar o APK do usuário).
- [x] `P7ProjectHistory.forget` rejeita URI inválida/não presente; preserva as permissões SAF, alterações pendentes e demais arquivos.
- [x] `P7ProjectHistoryInstrumentedTest` confere o menu contextual e a rejeição de remoção de entrada não autorizada.
- [ ] Conferir a captura da **Preview 11** Android 10/15 e comparar a integração do mascote contra o PNG oficial antes de declarar a correção visual homologada.

## Estado e limitações

- A Preview 11 continua uma **prévia de QA**, assinada com chave de testes. Não é 1:1 integral: tipografia/cores, imagens de tema, corpus de projetos reais e ferramentas criativas ainda necessitam avaliação visual e desenvolvimento.
- A `main` fica intacta; não promover OTA nem fazer merge automático.
- Não usar dados e logos inventados no histórico só para preencher os três cartões.
