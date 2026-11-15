# P7.45 — Isolar catálogo Design 135% sem reduzir os gates

Após perdas intermitentes do emulador Android 15 durante o teste instrumentado `enlargedTextRetainsCompleteThemeAndPresetLabels`, este estágio separa **exatamente esse método existente** numa classe de teste própria, com todas as mesmas asserções. O método continua usando a Activity real, 135% de texto, todos os 24 temas, presets, rótulos completos, linhas sem elipse, tamanho dos cartões, semântica de botão e restauração de SharedPreferences.

As funções auxiliares `byDescription` e `assertAccessibleButton` passam de `private` para **package-private somente no código androidTest**, garantindo a mesma lógica de acessibilidade nos dois arquivos sem copiar ou enfraquecer as verificações.

A matriz usa 6 sessões obrigatórias, com **25 seletores únicos**; a distribuição vira `1+1+1+1+42+116 = 162 testes/API`, em lugar de `1+1+1+43+116`. O passo isolado continua obrigatório e falha com `set -eu` se qualquer asserção, conexão ou comando falhar, sem repetição automática, bypass de screenshot ou modificação do APK.

A estratégia é preventiva contra um problema recorrente de infraestrutura, **não comprovação da causa-raiz**. O código do app e as validações de 14 imagens/API, 28 cross, compacto/200%, reboot API35, Source e OTA não mudam. Somente integrar após P7.44.2 passar em ambas as APIs e cross. Validação visual 1:1 e física Galaxy A55/TalkBack continuam NOT_APPROVED.
