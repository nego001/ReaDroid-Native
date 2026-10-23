# Referências oficiais P7 — NegrecoDroid

Os PNGs aprovados pelo proprietário **ainda não estão versionados**.
Não incluir imagens geradas de novo, capturas do emulador, thumbnails ou
imagens modificadas no lugar das referências oficiais.

Copiar, quando disponíveis, exatamente estes dois arquivos para esta pasta:

| Arquivo | Dimensões | SHA-256 |
| --- | --- | --- |
| `negrecodroid_controle_total_de_apks.png` | 1448×1086 | `d0232e8a93d793c5cde3d564f90c8c5ecdd870bee497558db0442bf98326461b` |
| `identidade_negrecodroid_em_neon_azul.png` | 1448×1086 | `25f93465b1ad0da45398201d9718cc070f3ba7fce11f84bf81e973c0b06d2765` |

Validar na raiz do repositório:

```sh
python3 tools/p7_reference_assets.py
```

**Um resultado PASS só é possível com os dois arquivos originais.**
Qualquer ausência, dimensão, CRC ou hash divergente bloqueia P7.0; não
substituir hashes automaticamente. A verificação do script em CI usa PNGs
sintéticos gerados apenas nos testes, não aceita mockups ausentes como
referências válidas. Depois da incorporação, executar comparação manual
de screenshots reais vs. os recortes oficiais no viewport definido na issue #11.

## Evidências automatizadas da matriz Android

Além das capturas do emulador, a matriz P7 gera o arquivo
`p7-evidence-android-29.json` ou `p7-evidence-android-35.json` via:

```sh
python3 tools/p7_capture_manifest.py
```

O manifesto exige **14 capturas reais por API (28 nas APIs 29 e 35)**:
oito no cenário normal (Início, Explorador vazio, Explorador com ZIP
**sintético de QA**, Segurança, Build, Design Studio, criador de ícones e
criador de logotipos), três em 320 dp/fonte 130% (Início, Explorador,
Design) e três em fonte 200% (as mesmas seções). Nenhuma captura
de um APK real do usuário é necessária para esse inventário.

A captura do Explorador populado é gerada em instrumentação isolada
após a suíte Android; ela valida o foco da Activity, a ausência da
sobreposição clara de sistema conhecida e a integridade do PNG. Em
conjunto, a suíte instrumentada e a captura isolada precisam passar.
O manifesto valida a estrutura CRC/IHDR/IEND do PNG, os dados dos
pixels, dimensões reais, cenário e SHA-256, com metadados de
densidade/API obtidos por ADB. Capturas inválidas ou ausentes fazem
o job falhar. Essa verificação **não** mede similaridade com as artes oficiais.

**Cuidado:** esse JSON documenta evidências reais de execução do emulador,
mas **NÃO aprova a fidelidade visual 1:1**, não substitui os dois PNGs aprovados
pelo usuário e não substitui homologação no Galaxy A55. Enquanto as referências
oficiais estiverem ausentes, o campo `official_references` será `BLOCKED`.

## Painel local de comparação humana

Após o workflow, cada artefato `p7-brand-android-29` e `p7-brand-android-35`
inclui, além das **14 capturas** e seu JSON de integridade, o arquivo
`p7-visual-review-android-{api}.html`. Extraia o ZIP preservando os PNGs na
mesma pasta e abra o HTML no navegador para inspecionar as imagens lado a lado
por cenário. É uma ferramenta **offline, sem JavaScript e sem chamadas de rede**.

O painel revalida o inventário contra os próprios PNGs antes da geração e
mostra as artes oficiais apenas quando o verificador exige e confirma os dois
SHA-256 originais. Se os PNGs aprovados não estiverem no repositório, indica
`BLOQUEADO`, sem substituir imagens por arte sintética ou capturas de CI.
Mesmo com as referências presentes, a análise 1:1 e o teste físico exigem
aprovação humana separada. O painel é gerado com:

```sh
python3 tools/p7_visual_review_board.py
```

A saída preserva os PNGs originais, não faz recortes automáticos ou inferência
de alinhamento entre uma arte de 1448×1086 e uma captura vertical.

## Resultado de aprovação e requisitos ainda abertos

O fluxo verifica 14 PNGs por API e gera um **único relatório cruzado com
28 imagens**. O painel offline é uma ferramenta para revisão humana e
não transforma a captura sintética, nem uma aprovação de CI, em prova
de fidelidade visual 1:1.

Os critérios de liberação continuam separados:

- **CI de Android**: testes instrumentados em API29/API35, captura
  isolada obrigatória, inventário completo e relatório cruzado
- **Artes oficiais**: incorporar somente os dois PNGs aprovados acima,
  com dimensões e SHA-256 idênticos; enquanto faltarem, `BLOCKED`
- **Aceite visual**: comparar manualmente as telas reais contra as
  referências no mesmo viewport; `NOT_APPROVED` até homologação explícita
- **Dispositivo físico**: executar e inspecionar no Galaxy A55; ainda
  `NOT_APPROVED`

Não confundir essas etapas com autorização de merge, distribuição
de APK ou publicação de OTA. O pipeline de UI é de **QA**, não de release.
