# NegrecoDroid — atualização P7 Preview 6

**Data:** 20/10/2026  
**Versão:** `3.0.0-preview.6-p7` / `versionCode 6`  
**Branch:** `feature/p7-negrecodroid-visual-foundation`  
**Revisão:** [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13), [P7 #11](https://github.com/nego001/ReaDroid-Native/issues/11)  
**Estado:** APK QA testável, sem merge na main e ainda sem aceite visual 1:1 integral.

## Duas correções reais diante do mockup aprovado

### Home: arte do mascote original, não redesenho
- [x] O desenho abstrato de `P7MascotView` foi substituído por **recorte da própria referência aprovada**, com capuz, olhos ciano e roupa. O desenho vetorial permanece como fallback se o Android não conseguir abrir o recurso.
- [x] `app/src/main/assets/p7_reference_mascot.webp.base64`: WebP de 160 px de largura, derivado de `negrecodroid_mascot_reference_clean.png` recortando o personagem, sem a engrenagem de configurações.
- [x] SHA-256 dos pixels compactados/WebP original incorporado: `0f5817509df5f6b19c01e9ab124d7667878a2bab5500e34954eb7d59ac1e0713`.
- [x] O arquivo é empacotado localmente: nenhum HTTP/download em tempo de execução; decodificação Base64 e BitmapFactory em `P7MascotView`.
- [x] Mascote exibido com proporção vertical sem esticar; tamanho ampliado no cartão de boas-vindas.
- [x] `P7MascotArtworkInstrumentedTest` confere SHA-256, resolução, decodificação Android e a presença do recurso efetivo, nas APIs 29 e 35.

### Explorador: chips com nomes exatos da referência
- [x] Chips no topo: **Todos / Smali / Recursos / Imagens / XML**, na ordem do mockup.
- [x] Smali filtra arquivos `.smali` realmente presentes no APK; **não implica que o app tenha decompilado o DEX**.
- [x] Imagens: `.png`, `.webp`, `.jpg`, `.jpeg`, `.gif`, `.bmp`. XML: `.xml`.
- [x] O navegador tradicional e as consultas SQL paginadas usam os mesmos filtros. O menu avançado mantém Bibliotecas, DEX, Assets, Manifesto, Editáveis e Alterados.
- [x] `P7ExplorerChromeInstrumentedTest` passou a validar os chips e um caminho XML editável.
- [x] `P7IndexedFiltersInstrumentedTest` constrói um APK sintético com arquivos de diferentes tipos, valida os totais e garante que o índice não retorna arquivos fictícios.

## Entrega/testes

- `Android APK`: build QA assinado com chave debug, pacote `com.readroid.app.qa` isolado da versão principal `com.readroid.app`.
- `Source checks`, `OTA manifest validation` e `P7 NegrecoDroid brand validation` (Android 10/15).
- Evidências de Home/Explorador/Design vêm do mesmo commit compilado. Não interpretar testes automatizados como aprovação visual humana.
- **Não fazer merge automático, publicar OTA ou afirmar que o APK está pronto para produção.**

## Ainda diferente da imagem

- A arte do mascote foi recortada da tela de apresentação (fonte relativamente pequena); ela é visualmente mais fiel do que o substituto vetorial, mas o layout completo da Home ainda precisa de comparação lado a lado.
- O histórico persistente de vários projetos não foi implementado nesta etapa. Contadores de builds/ameaças continuam vazios quando não existem dados reais.
- Galerias nativas do Design Studio ainda têm miniaturas aproximadas; editores completos de ícones e logos seguem pendentes.
- Os PNGs inteiros das duas referências aprovadas ainda não foram incorporados à árvore GitHub como arquivos binários, apenas a arte compactada do mascote.
- Falta aprovação física no Samsung Galaxy A55 e checklist de dimensões/cores da captura real.

## Registro de regressões e capturas desta versão

- A revisão da captura Android 15 do primeiro mascote encontrou uma sobreposição temporária do diálogo **Pixel Launcher isn't responding**. A captura ocorreu antes do script de recuperação específico do emulador; isso **não foi identificado como travamento do NegrecoDroid**. O workflow passou a verificar que a Home está visível e rejeitar a sobreposição antes de salvar a imagem.
- O primeiro teste de filtro XML falhou porque tentou adicionar ao plano um `res/config.xml` não suportado pelo editor textual. Mantido o bloqueio real do `EditPlan`; agora o teste valida o XML como navegação e usa `assets/a.txt` para testar edição, sem relaxar a política de formatos.
- Os chips seguem a ordem do mockup; a consulta SQLite real de extensões tem um teste independente de índice para prevenir regressão.
- O mascot vem **da própria referência**, mas o crop original é uma fonte de baixa resolução; não o anunciar como ilustração vetorial ou pixel-perfect redimensionada.
