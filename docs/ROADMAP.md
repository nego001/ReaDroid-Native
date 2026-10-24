# NegrecoDroid — panorama vigente em 22/10/2026

> **Fonte de acompanhamento atual:** [PR P7 #13](https://github.com/nego001/ReaDroid-Native/pull/13), [issue visual #11](https://github.com/nego001/ReaDroid-Native/issues/11), e [changelog contínuo sem APK](P7-DESENVOLVIMENTO-CONTINUO-SEM-APK.md).
> O quadro antigo abaixo documenta o planejamento inicial; seus checkboxes e o antigo “build blocker” **não representam o estado atual**.

## Visão futura do produto (planejamento, não implementada)

A [issue #17](https://github.com/nego001/ReaDroid-Native/issues/17) registra o objetivo de evoluir o NegrecoDroid para uma **plataforma modular, multiplataforma e multiagente** que automatiza estudos autorizados de executáveis e produz **ZIPs verificáveis, utilizáveis por qualquer IA**. A arquitetura detalhada está em [visão do produto](NEGRECODROID-VISAO-PLATAFORMA-MULTIAGENTE.md) e [RFC de agentes/plugins](NEGRECODROID-RFC-MODULOS-EVIDENCIAS.md). **Não substituir a etapa P7 corrente nem declarar essas capacidades prontas.**

### Leitura distribuída em módulos (visão futura)

**Nova decisão de arquitetura:** dividir a análise por partes estruturais do arquivo (ex.: manifestos, recursos, código, funções e dependências) entre leitores que operam **simultaneamente** quando seguros, e reunir tudo com evidências, cobertura e revisão cruzada. Não é simplesmente quebrar bytes de um executável e tratá-los como programas independentes. Especificação e critérios de aceite: [RFC de leitura distribuída](NEGRECODROID-RFC-LEITURA-DISTRIBUIDA.md). A implementação fica em uma trilha futura; **a P7 atual mantém prioridade**.

## Onde estamos

**P7.6 em desenvolvimento**, com P7.5 funcional e P7.7 visual/física ainda pendentes. Há base nativa para Home, Explorador com índice e filtros, navegação de cinco abas, Design Studio inicial, histórico local verdadeiro, edição textual suportada, exportação de ZIP APK **sem assinatura**, verificação SHA-256 e recuperação criptografada. Isso **não** é um editor/decompilador completo de APK nem versão final.

- **Última base verificada:** commit `d8f70a2f`, [CI Android 10 e 15](https://github.com/nego001/ReaDroid-Native/actions/runs/39891669987), 131/131 testes instrumentados por API, smoke de Design e 13 capturas por API; Source e OTA aprovados. `references=BLOCKED`, `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`. Outros commits precisam de validação própria.
- **P7.0:** ainda faltam no GitHub os dois PNGs completos da arte de referência aprovada e seus recortes/medidas para o viewport de comparação 1:1.
- **P7.1–P7.4:** implementações funcionais iniciais; falta conferir correspondência visual final da Home, Explorador, identidade e Design Studio.
- **P7.5:** Criador de Ícones e Logo Studio exportam PNG e SVG; 24 combinações de temas e 12 opções de layout implementadas, testadas em API29/API35 na base `a9c0b277`. O catálogo atingiu a meta de quantidade; não corresponde a 12 sistemas visuais inteiramente distintos. Ainda faltam referências PNG e avaliação 1:1.
- **P7.6:** grade responsiva, Home expansível, contraste do tema claro, prévias e botões acessíveis, cinco presets, miniaturas e títulos otimizados, catálogo de 24 temas com descrições completas validados. Anúncio real da identidade no Logo Studio, texto expandido e smoke pós-cancelamento em nova CI; faltam desempenho físico, TalkBack manual, comparação 1:1 e regressões finais.
- **P7.7:** testar no Samsung Galaxy A55 físico e obter aprovação do proprietário antes de integrar a PR.
- **Além da P7:** engenharia reversa/decompilação DEX/Smali, edição visual avançada de recursos, zip alignment, assinatura local v2/v3 e verificação de instalabilidade, assistente inteligente planejado, QA end-to-end e política de lançamento estável. A ordem e escopo devem ser confirmados quando cada fase começar.

## Critério para encerrar

Terminar a **P7** exige equivalência visual medida contra PNGs oficiais, comportamento funcional e acessível, CI final verde e aprovação física. Terminar o **app completo** exige também o motor avançado de edição/rebuild/decompilação/assinatura e suas validações. Não há percentual nem data tecnicamente confiáveis enquanto esses escopos permanecerem abertos.

**Política atual:** PR #13 rascunho, `main` inalterada, sem `versionCode` novo nem geração/publicação de APK automático em commits menores. OTA não está habilitada para distribuição.

---

## Histórico de planejamento inicial (não atualizado)

# ReaDroid Native roadmap

## P0: Core APK inspection
- [x] APK selection using Android Storage Access Framework
- [x] SHA-256, DEX and native library inventory
- [x] PackageManager-based manifest inspection
- [x] Requested permissions and exported component inventory
- [x] Explanatory initial security findings
- [ ] Successful Android APK build in GitHub Actions
- [ ] Binary XML decoding independent of PackageManager
- [ ] Test fixtures and automated scanner unit tests
- [ ] APK signature scheme v2/v3 verification

## P1: File explorer and version comparison
- [ ] Interactive searchable ZIP explorer
- [ ] Side-by-side version differences

## P2: Decompilation
- [ ] DEX metadata browser
- [ ] Compatible embedded decompiler

## P3: Visual APK editor
- [ ] Resource previews and supported edits
- [ ] Modification tracking and backups

## P4: Rebuild and signing
- [ ] Resource rebuild and zip alignment
- [ ] Local signing and signature validation

## P5: Intelligent assistant
- [ ] Offline rule-based findings explanations
- [ ] Optional on-device inference

## Build blocker
GitHub Actions runs currently fail before any step starts; the last checked run has runner_id 0 and an empty steps array. Check repository Actions policies, runner availability, and billing/usage restrictions in GitHub Settings. A successful build has not yet been observed.
