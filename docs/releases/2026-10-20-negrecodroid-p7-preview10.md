# NegrecoDroid — P7 Preview 10 (correção visual após screenshots reais)

**Data:** 20/10/2026  
**Versão QA:** `3.0.0-preview.10-p7-qa` / `versionCode=10`  
**Pacote isolado:** `com.readroid.app.qa`  
**Origem:** [PR #13](https://github.com/nego001/ReaDroid-Native/pull/13)  
**Referência obrigatória:** arte das três telas aprovada e descrita na [Issue #11](https://github.com/nego001/ReaDroid-Native/issues/11)

## Defeito encontrado na Preview 9

A captura da Home **real** no Android 15 mostrou que o cartão opaco de saudação cobria o corpo do mascote, deixando só a cabeça visível acima dele. Os testes automáticos tinham passado porque validavam presença, navegação e texto, não a composição visual. O PNG aprovado continha também uma engrenagem ilustrada, que ficava duplicada com a engrenagem real implementada na Home.

Essa diferença não foi atribuída falsamente ao emulador: era um erro visual de ordem de desenho da interface.

## Alterações efetivamente aplicadas na Preview 10

- [x] `P7MascotView`: permanece com o **asset original aprovado**, porém desenhado acima do cartão por elevação de camada Android. O bitmap não deixa de ser parte da interface nativa interativa; os componentes continuam reais.
- [x] O glyph da engrenagem duplicado dentro do recorte promocional é ocultado **somente na porção superior direita do bitmap**, usando Canvas `clipOutRect` (API mínima Android 8.0/API26). A engrenagem verdadeira da toolbar continua clicável.
- [x] `StudioDashboard`: `mascot.setElevation(...)` corrige o Z-order sem aumentar a altura do cartão ou transformar a Home inteira num screenshot.
- [x] Ícones dos **seis atalhos** substituídos por vetores específicos, na ordem do mockup: Abrir APK (pasta), Analisar (lupa), Build APK (ferramenta), Decompilar (código), Editar Smali (documento), Assinar APK (escudo). Nada de reutilizar ícones de abas sem relação.
- [x] Atalhos continuam com ações existentes ou avisos honestos onde ainda não há função completa.
- [x] Os testes instrumentados da Home, navegação, histórico SAF, filtros SQLite e Design Studio permanecem obrigatórios em Android 10/API29 e Android 15/API35.
- [ ] Nova captura real com corpo do mascote aparecendo sobre o cartão e ausência de engrenagem duplicada, para aceite de **esta** revisão, não de uma anterior.

## Compatibilidade e cautelas

- APK QA paralelo; não substitui dados nem instalação principal. A chave debug **não é certificado de produção**.
- Nenhuma mudança nesta entrega em arquivos do usuário, índice SQLite, cofre, SAF, planos de edição ou verificação de assinatura.
- Histórico multientrada e ícones reais de projetos vieram das Previews 7/8 e foram preservados.
- **Ainda não é 1:1 homologado:** não temos screenshots aprovados de uma Home com três projetos reais no Galaxy A55, nem o catálogo/editor criativo completo, nem os PNGs de referência integrais versionados como binários.
- Não publicar OTA, não integrar à `main` e não encerrar a [Issue #11](https://github.com/nego001/ReaDroid-Native/issues/11) só porque um APK compilou.

## Verificações de entrega

Registrar URLs de `Android APK`, `Source checks`, `OTA manifest validation` e `P7 NegrecoDroid brand validation` do **mesmo commit final**. Revisar as capturas das três telas e corrigir discrepâncias antes de afirmar reprodução literal.
