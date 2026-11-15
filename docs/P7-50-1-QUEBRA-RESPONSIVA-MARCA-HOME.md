# P7.50.1 — subtítulo da Home responsivo sem perder conteúdo

## Origem (25/10/2026)

A auditoria de `p7-compact-inicio-android-35.png` do artefato oficial da [matriz P7.49.1 #40172063473](https://github.com/nego001/ReaDroid-Native/actions/runs/40172063473) identificou um desvio concreto em viewport **320 dp e fonte do sistema em 130%**: o texto de marca `ANÁLISE, EDIÇÃO E CUSTOMIZAÇÃO DE APKS` quebrava em um trecho final com apenas `APKS`. A Home normal deve preservar a identidade aprovada e o texto salvo pelo usuário.

## Modificação nativa (somente Home)

- A função `MainActivity.brandSubtitleForViewport` mantém a frase oficial completa na Home padrão e seleciona uma quebra semântica intencional **apenas** abaixo de 360 dp quando a escala efetiva de fonte é ≥118%: `ANÁLISE, EDIÇÃO E\nCUSTOMIZAÇÃO DE APKS`.
- A descrição de acessibilidade da legenda fala a frase **sem quebra**, para manter leitura correta do TalkBack.
- Subtítulos personalizados (incluindo vazio) retornam **exatamente** como salvos, sem abreviação, substituição ou escrita em preferências. Nome `NegrecoDroid` permanece intacto.
- Nenhum APK, arquivo SAF, SQLite, fluxo de exportação, assinatura, OTA, versão, histórico ou recurso gráfico da marca é modificado. É texto exibido no cabeçalho da Home, não imagem estática.

## Regressão e homologação

Novo teste instrumentado `P7HomeOverviewInstrumentedTest.narrowBrandTaglineKeepsEveryWordAndCustomSubtitles` confere 320/359/360/393 dp, fontes normais e ampliadas, frase integral e personalização livre. A meta da matriz passa de **166 para 167 testes instrumentados por API** (6 isolados, 44 de navegação e 117 no bloco restante), sem remover nenhum teste anterior. Seguem obrigatórios 14 PNGs/API e comparação cruzada 28/28, viewport 320 dp/fonte 130%, 200% e reboot da API35.

**Status:** staging, não aprovada pela CI. Não chamar de homologação visual 1:1; o mockup aprovado ainda exige verificação de proporções, logo, ícones, miniaturas e acabamento nos três painéis, além do ensaio físico Galaxy A55/TalkBack. PR #13 em draft, sem merge na `main` ou instalação/publicação de APK/OTA.
