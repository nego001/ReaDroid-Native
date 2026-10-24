# P7.22 — Opções do Explorador reconhecidas como botão pelo TalkBack

## Situação real e evidência

No `P7ExplorerEntryRow` da P7, a área `⋮` já tinha `contentDescription="Opções de <nome>"`, foco, click listener e área de 48×48dp; porém era um `TextView` anunciado com papel de texto em vez de um `Button`. A lista mantém a separação entre tocar a linha (abrir arquivo/pasta) e tocar o `⋮` (abrir opções).

A P7.21 já havia substituído caixas individuais por divisórias horizontais sem modificar os callbacks. A P7.22 ajusta a semântica assistiva **sem alterar a renderização normal, a busca, os dados ou a lógica de APK**.

## Alteração na branch da PR #13

- `P7ExplorerEntryRow.java`: fixa `IMPORTANT_FOR_ACCESSIBILITY_YES` no `⋮` e expõe a classe `android.widget.Button` pelo `AccessibilityNodeInfo`, mantendo o mesmo `TextView`, a descrição real `Opções de <nome>`, o foco, as dimensões de toque e o listener existente.
- `P7ExplorerEntryRowInstrumentedTest.java`: valida **papel Button**, texto completo e propriedade `isClickable` via nó Android real, para pasta e arquivo modificado; valida que as opções **não invocam** a ação de abrir a linha.
- O teste anterior da P7.21 para separador no rodapé, altura mínima, geometria e rótulos permanece válido.

## Validação exigida

- [ ] Source checks e OTA no **HEAD** da P7.22.
- [ ] Matriz instrumentada Android 10/API29 e Android 15/API35 com o teste de acessibilidade atualizado e os testes existentes.
- [ ] Screenshots de Explorador normal/sintético/compacto/fonte 200% para verificar a P7.21 sem regressões na P7.22.
- [ ] Revisão TalkBack **manual** no Samsung Galaxy A55 para confirmar anúncio e ordem de foco. Teste automatizado não é substituto.

**Restrições:** referência oficial `VERIFIED` não significa `visual_1to1=APPROVED`; aprovação visual e `physical=APPROVED` só com evidência/revisão humana. Nada de merge para main, APK, versionCode, instalação, assinatura, OTA ou execução de arquivo fornecido. REA permanece integração futura isolada da P7.
