# NegrecoDroid — P7 Preview 8: ícones reais de projetos recentes

**Data:** 20/10/2026  
**Versão:** `3.0.0-preview.8-p7` / `versionCode 8`  
**Branch de implementação:** `feature/p7-negrecodroid-visual-foundation`  
**Referência visual:** três telas aprovadas na [Issue #11](https://github.com/nego001/ReaDroid-Native/issues/11).  
**Entrega:** APK QA independente, sem merge na `main`, **não homologado como reprodução 1:1 final**.

## Implementado neste ciclo

1. Ícone real de APK no histórico: `P7RecentAppIcons` consulta a tabela de recursos do arquivo selecionado por meio do `PackageManager` e desenha a imagem declarada no manifesto Android. Não instala, executa nem confia em aplicações do conteúdo.
2. Ícones compactados em miniaturas privadas de **64 × 64 px**, vinculadas a um nome SHA-256 da URI SAF. As imagens são associadas somente a documentos com **permissão persistida de leitura**.
3. Se o pacote não informar ícone ou estiver quebrado, o histórico usa `ic_p7_file` vetorial. **Não inventar ícones oficiais de Spotify, Netflix, YouTube ou outros aplicativos**.
4. `P7HomeOverview` mostra até três projetos (nome, pacote, data e ícone) como no layout aprovado.
5. A limpeza do histórico também remove os thumbnails privados; entradas removidas após o limite de 12 também têm as imagens antigas eliminadas.
6. Segurança: tamanho máximo de cache por ícone, decodificação com limite de 128 px, pasta privada, sem permissão extra, backup Android desabilitado e aplicação da mesma política SAF da Preview 7.
7. `P7RecentAppIconsInstrumentedTest`: lê o ícone real do APK do próprio aplicativo nos emuladores Android 10 e 15 e verifica ausência de gravação para URI sem autorização / arquivo inválido.

## Validação e limites

- A aplicação de personalização, o plano de edição, a cópia temporária do APK, as assinaturas, o índice SQLite e a importação SAF não foram modificados funcionalmente por esta entrega.
- Arquivos APK que ocultam ou não fornecem ícone utilizam o fallback. A identidade visual do app na Home depende do ícone disponível no arquivo real selecionado.
- O histórico precisa ser preenchido pelo próprio usuário para gerar capturas comparáveis à arte com três projetos; sem arquivos selecionados, a tela vazia é legítima.
- Ainda faltam reprodução visual literal integral (proporções e tipografia), ícones e logos editáveis, catálogo expandido e homologação física no Galaxy A55.
- Evidência de CI, SHA-256 e número do APK de teste devem ser registrados para o commit final específico, não presumidos a partir de versões anteriores.
