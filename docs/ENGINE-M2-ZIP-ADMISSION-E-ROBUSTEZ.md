# Motor M2.1 — admissão consistente de metadados ZIP potencialmente hostis

A decisão atual do projeto é **motor primeiro, interface por último**. A M1
concluiu a CI dedicada com 3/3 jobs no SHA `fc2fc564`, validando edição
textual, reconstrução e exportação SAF de uma fixture **sem assinatura**. M2
não muda a UI, não habilita assinatura, nem lança APK ou OTA.

## Lacuna auditada

`ApkExplorer.inspect()` preenchia um JSONArray de até 150 mil registros,
mas seu verificador de path aceitava formas como `assets/./file` e
`assets//file`, que o índice `ApkDiskIndex` rejeitava.
Ambos liam o **tamanho descomprimido declarado** do diretório ZIP, porém
não rejeitavam tamanho desconhecido ou expansão muito alta declarada.
Isso podia gerar avaliações incompatíveis e trabalho desnecessário com
arquivos suspeitos antes da catalogação.

## Mudança M2.1

- Novo `ApkZipAdmission`, verificador **comum** ao JSON Explorer e à
  criação do índice SQLite. Valida nome relativo, sem elementos `.`,
  `..`, segmento vazio interior, barras invertidas, caracteres de
  controle, mais de 128 níveis ou mais de 4096 caracteres.
- Exige tamanhos comprimido e descomprimido conhecidos e não negativos,
  método STORED ou DEFLATED, coerência STORED, tamanho por entrada de até
  **1 GiB**, soma declarada de até **2 GiB**, e mantém o teto de
  **150 mil entradas**. Diretores vazios STORED/DEFLATED continuam aceitos.
- Rejeita uma taxa **declarada** de descompressão acima de **1000:1**
  quando o tamanho resultante é de 16 MiB ou mais. Esta é uma política
  conservadora que poderá rejeitar ZIPs excepcionalmente compressíveis;
  não deve ser afrouxada sem testes adicionais de streaming.
- `ApkDiskIndex.build()` verifica a entrada antes da escrita SQLite.
  Na falha, a transação é interrompida e o banco parcial é removido
  pelo `finally` existente. Nenhuma entrada é extraída para disco.
- `ApkExplorer.inspect()` aplica a política antes de adicionar itens
  JSON. Os dois caminhos agora rejeitam consistentemente ZIPs suspeitos.

## Limites da proteção

**Metadados podem mentir.** Admissão de metadados não verifica o CRC real
nem garante que o descompactador não expanda mais que o cabeçalho anuncia.
Leituras de prévia e inspeção continuam com limites individuais;
reconstrução M1 ainda verifica CRC/SHA-256 antes do commit atômico.
Uma etapa posterior M2 deve cobrir **contagem real de bytes extraídos**
durante a análise completa, tratamento de provedores SAF problemáticos,
cancelamento de importação e relatórios de progresso. Nenhuma alegação de
imunidade universal a ZIP bombs é autorizada nesta fase.

## Evidências exigidas

- Testes instrumentados `ApkZipAdmissionInstrumentedTest`: ZIP legítimo
  aceito nos dois exploradores; ZIP real com ~17 MiB de zeros compactados
  rejeitado **nos dois** sem deixar SQLite parcial; tamanhos desconhecidos,
  métodos estranhos, paths perigosos, diretórios vazios válidos e aritmética
  de limite 2 GiB.
- Também rodar a suíte `ApkDiskIndexInstrumentedTest` existente, que
  cobre paginação, diretórios inferidos, rollback e índice obsoleto.
- Matriz específica do Android 10/API29 e Android 15/API35.
- PR M2 em rascunho sobre a branch da M1 validada. `main` intacta e
  PR de interface #13 congelada. Nenhum APK/OTA distribuído.
