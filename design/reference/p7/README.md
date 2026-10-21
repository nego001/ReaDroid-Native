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

O manifesto exige onze screenshots por API: Home, Explorador, Design Studio,
editor de ícones, editor de logotipo, três capturas a 320dp/fonte 130% e três
a fonte 200%. Ele verifica a estrutura CRC/IHDR/IEND do PNG, dimensões reais,
cenário e SHA-256 de cada arquivo e inclui os metadados de densidade/API
obtidos por ADB. Qualquer captura ausente ou inválida faz o job falhar.

**Cuidado:** esse JSON documenta evidências reais de execução do emulador,
mas **NÃO aprova a fidelidade visual 1:1**, não substitui os dois PNGs aprovados
pelo usuário e não substitui homologação no Galaxy A55. Enquanto as referências
oficiais estiverem ausentes, o campo `official_references` será `BLOCKED`.
