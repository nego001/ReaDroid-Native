# NegrescoDroid | Motor M3.2 — leitura controlada do mapa de seções DEX

**Base:** M3.1 (PR #29), validada no SHA `c27db6d9adccc03dc894393c77107c51c0dc8cb3`. Esta etapa não altera interface, assinatura nem a `main`. Não publicar APK/OTA.

## Objetivo e implementação

O novo `DexMapProbe` lê `map_list` de DEX tradicionais **035–040**, somente depois das checagens do cabeçalho. Usa `InputStream` em fluxo; não lê o arquivo inteiro, não interpreta classes/métodos e nunca executa bytecode. A M2 continua responsável por verificar CRC e comprimentos reais da entrada ZIP **antes** do scanner.

O formato é composto por um contador de 32 bits seguido por `map_item` de **12 bytes** (`type` u16, `unused` u16, `size` u32 e `offset` u32). O leitor exige:

- Até **64 entradas** do mapa, com comprimento total checado antes de percorrer a lista;
- `map_off` válido e a no máximo **16 MiB** desde o começo do DEX. Mapas de DEXs maiores podem aparecer como não suportados, sem que o APK seja rejeitado;
- Seções com tipos conhecidos, contagens positivas, tipos exclusivos, campos reservados zerados e offsets estritamente crescentes;
- `header_item` inicial com offset zero, `map_list` presente e apontando para `map_off`;
- Seções de tamanho fixo sem sobreposição; comparação das contagens e offsets declarados no cabeçalho com as seis tabelas de identificadores presentes no mapa;
- Interrupção propagada por `InterruptedIOException` e bloqueio de streams truncados/sem progresso.

A estrutura do `SecurityScanner` inclui `dexMapPreview` para **até quatro DEX**, contendo apenas rótulos de seções de uma lista fixa, contagens e offsets. O status `map-only` significa que o *mapa declarado* passou nas checagens estruturais, **não** que o corpo do DEX seja válido. `unreadable-map` sinaliza problemas ou características ainda não suportadas sem interromper a inspeção do arquivo APK. `dexMapPreviewTruncated` informa quando há mais DEX do que os quatro mostrados.

## Limites relevantes

- Não há descompilação, montagem, edição DEX, análise de métodos, decodificação de instruções, interpretação da lista completa de classes, validação de assinatura interna, teste de carregamento pelo Android ou garantia de instalabilidade.
- As seções variáveis do DEX exigem parsers próprios. A M3.2 verifica apenas seus offsets básicos e a coerência do mapa, **não** a extensão real desses blocos.
- O teto de 16 MiB é um **limite de leitura da prévia**, não o limite de tamanho de importação do APK. Os limites ZIP existentes de 1 GiB de origem e 2 GiB descomprimidos continuam valendo.
- Tipos desconhecidos e DEX 041 são tratados como não suportados pela prévia. O objetivo é falhar de modo conservador, sem inventar suporte ao formato.
- O novo leitor não altera a transação de rebuild M1 nem a exportação SAF.

## Testes Android e evidências

`DexMapProbeInstrumentedTest` cobre mapas válidos, concordância cabeçalho/mapa, tipos repetidos, offsets fora de ordem, mapa ausente, seções desconhecidas, campo reservado indevido, contadores adulterados, limite de leitura, cancelamento e integração do scanner com DEX válido para a prévia e DEX inválido.

A matriz M2/M3 executa Android 10/API29 e Android 15/API35; regressões M1 continuam obrigatórias. Contratos Python verificam limites e ausência de leitura integral. Source checks e OTA devem passar **no SHA exato** antes de homologar a PR. Não gerar nem distribuir APK.

**Referência normativa:** https://source.android.com/docs/core/runtime/dex-format
