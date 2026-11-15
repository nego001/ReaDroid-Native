# NegrecoDroid P7 — Preview 9: fidelidade da Home

**Data:** 20/10/2026  
**Versão Android:** `3.0.0-preview.9-p7` (`versionCode=9`)  
**Pacote isolado de testes:** `com.readroid.app.qa`  
**PR em desenvolvimento:** [#13](https://github.com/nego001/ReaDroid-Native/pull/13)  
**Referência 1:1 exigida:** [#11](https://github.com/nego001/ReaDroid-Native/issues/11)

## Mudanças efetivamente programadas

1. **Header operacional:** menu hamburger no canto superior esquerdo e engrenagem de personalização no direito, com ícones vetoriais reais, alvos de toque de 38dp e rótulos TalkBack. O menu abre destinos existentes (Abrir APK, Explorador, Segurança, Build e Design); a engrenagem abre a tela real do Design Studio.
2. **Boas-vindas mais fiel:** cartão de saudação compacto, ilustração original do mascote em camada sobreposta ao cabeçalho, tal como a arte aprovada. Reduz o espaço consumido pela ilustração e deixa estatísticas/histórico/atalhos mais visíveis sem usar uma imagem estática de toda a tela. A fonte ampliada recebe altura extra para evitar corte.
3. **Estatísticas 2×2:** cada cartão passou a ter ícone à esquerda e número + legenda empilhados à direita, reproduzindo a composição do mockup. Recursos vetoriais de cubo, arquivo, ferramenta e escudo.
4. **Navegação inferior:** removido o retângulo azul gigante atrás da aba ativa. Agora a seleção usa um traço azul discreto **acima** do ícone, mais cor no ícone e no texto. O contorno de foco teclado/DPAD continua acessível.
5. **Regressão automática:** `P7NavigationInstrumentedTest` testa menu/engrenagem e a barra com indicador azul. `P7HomeOverviewInstrumentedTest` exige estrutura horizontal dos cartões. O script `tools/p7_home_smoke.py` confere os seis atalhos, componentes na primeira tela e navegação de menu/settings em Android 10/API29 e Android 15/API35.

## Segurança e funcionalidade preservadas

- Menus e atalhos chamam fluxos existentes; operações ainda não disponíveis não são anunciadas como concluídas.
- Histórico de APKs por SAF, ícones autênticos, SQLite paginado, plano de edições, exportação e mecanismos de recuperação da Preview 8 não foram alterados nesta rodada.
- Nenhum dado de projetos, builds ou detecções de ameaças é inventado para imitar a imagem promocional.
- A versão QA instala separadamente da principal, sem migração obrigatória.

## O que ainda impede declarar 1:1 completo

- A saudação e a posição final do mascote exigem comparação da **captura real da Preview 9** lado a lado com o recorte da imagem fornecida.
- A Home precisa de teste físico com três APKs reais no histórico, pois estados vazios não reproduzem os exemplos promocionais.
- Alguns ícones das ações rápidas ainda são genéricos, miniaturas do Design Studio ainda diferem da fonte e não há editor completo de logos/ícones.
- Os PNGs oficiais integrais ainda não estão versionados como binários no GitHub.
- A compilação e a matriz Android 10/15 do **commit final** precisam constar como aprovadas antes de promover esta versão.

**Decisão:** manter a PR em rascunho, não integrar à `main` e não habilitar publicação OTA da Preview 9 até revisão visual e QA.
