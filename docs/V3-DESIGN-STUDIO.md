# V3 • NegrescoDroid Studio OLED (prévia de desenvolvimento)

## Objetivo
Implementar em UI Android nativa o modelo visual escolhido pelo usuário: base OLED preta,
destaques azuis/neon, cabeçalho com identidade, cartão de projeto, atalhos visuais,
painel de personalização em duas colunas e ações técnicas organizadas.

A referência artística é uma direção de design; o layout é adaptável às dimensões
reais dos celulares. Não é uma captura de tela usada como plano de fundo.

## Implementado
- [x] Nova branch isolada `feature/v3-design-studio`, baseada em `feature/ota-seguro`.
- [x] Marca de cubo, cabeçalho compactado e destaque em `Droid`.
- [x] Cartão do projeto atual com informações reais e botão de seleção de APK.
- [x] Cubo APK neon desenhado via Canvas nativo, sem bitmap, blur ou animações pesadas.
- [x] Quatro atalhos 2×2 com ícones vetoriais, legenda e atalho favorito em primeiro.
- [x] Painel de personalização expansível, com cartões 2×2 preservando callbacks existentes.
- [x] Cor personalizada em hexadecimal #RRGGBB, temas, escala tipográfica e densidade.
- [x] Modos de superfície neon/minimalista e cantos personalizáveis.
- [x] Exportação/importação do novo conjunto de preferências, com validação e compatibilidade com presets antigos de esquema 1.
- [x] Cartões de ações e cabeçalhos explicativos nas abas Construir, Segurança e IA.
- [x] Lista de arquivos com cartões e tipografia de metadados mais legível.
- [x] Paginação do explorador corrigida para realmente renderizar itens além dos 120 primeiros.
- [x] Regressão de paginação com 145 entradas em View Android real.
- [x] Testes Android de exportação/importação visual, com round-trip de 11 preferências e compatibilidade com presets antigos.
- [x] Importador com tipos JSON estritos, sem coerção silenciosa nem caracteres de controle na identidade.
- [x] Testes Android de reconstrução sem assinatura: alteração textual, preservação do original, remoção de assinaturas antigas, rejeição de caminhos inseguros e edições inexistentes.
- [x] Dez testes instrumentados executados com sucesso no Android API 29.
- [x] OTA mantém avisos verdadeiros sobre configuração incompleta e sem instalação automática.
- [x] Navegação inferior com seleção visual em cartões e descrições acessíveis.
- [x] Ajuste de contraste WCAG nos botões, aviso para cor HEX pouco legível.
- [x] Resumo do projeto reduzido; dados técnicos completos permanecem no relatório.
- [x] Troca de tema/rotação retêm APK, relatório e plano textual na mesma sessão.
- [x] Recuperação do arquivo selecionado quando a análise é interrompida pela recriação da Activity.
- [x] Estado aberto/fechado do painel de personalização persistido separadamente.
- [x] Teste no emulador Android (API 29): APK instalado, Início → Arquivos → Segurança → Início, captura de tela gerada.
- [x] Correção da automação: shell POSIX e detecção de crashes tratada pelo script Python.
- [x] Tema Android e cores da barra de status/navegação alinhados à preferência visual.
- [x] Botão Voltar nas outras abas retorna para Início.

## Restrições
- **Não** criar funcionalidades de assinatura APK que o programa ainda não suporta.
- **Não** alterar certificado de APK, chaves, análise de segurança nem as permissões Android.
- Mudanças visuais devem preservar controles, callbacks e resultados técnicos.
- Preferências personalizadas devem continuar funcionando nos temas claro e grafite.
- Nenhuma versão final V3 deve ser publicada automaticamente.
- A arte referência tem brilhos e detalhes decorativos que foram reinterpretados com
  gradientes e desenho vetorial, para evitar consumo excessivo de GPU/CPU.

## Nova fase de regressões
- 10/10 testes instrumentados aprovados no workflow da revisão `abb61da5`: https://github.com/nego001/ReaDroid-Native/actions/runs/39188439031
- A simulação visual de 320dp e fonte do sistema em 130% exige que o APK seja reinstalado após os testes instrumentados. O fluxo foi ajustado e aguarda confirmação final.
- Os testes de reconstrução validam apenas um **ZIP APK sem assinatura**. Não demonstram que o resultado instala no Android.
- O recurso de exportação/importação JSON foi exercitado diretamente no Android. O fluxo completo de escolha de arquivos pelo sistema ainda requer um teste manual de UX.

## Validação
- [x] Builds Android intermediários concluídos com sucesso na branch.
- [x] Confirmada compilação Android e verificação de código após `2ebf8208`.
- [x] Examinar a captura real do emulador da primeira execução que abriu e navegou corretamente.
- [x] Workflow de smoke aprovado no commit `2ebf8208` (Android API 29): instalação, abertura, navegação, screenshot e ausência de erros AndroidRuntime.
- [ ] Abrir em celular físico, tocar em todas as opções e conferir rolagem/áreas de toque.
- [x] Seleção SAF de APK real pelo DocumentsUI, análise e exploração de pastas/arquivos em emulador API 29.
- [x] Troca OLED → Claro com um projeto aberto, sem perder os dados do APK.
- [ ] Testar exportação, importação de presets e o fluxo de edição de arquivos com APK real.
- [x] Capturas reais dos temas OLED e Claro, com contraste e navegação visivelmente corretos em emulador.
- [x] Teste automatizado com tema Claro, fonte a 130%, modo compacto e retenção do APK aprovado no emulador.
- [ ] Testar largura de 320–360 dp e telas físicas de diferentes fabricantes.
- [ ] Testar importação de presets anteriores e do novo conjunto.
- [ ] Confirmar que o código OTA permanece bloqueado quando não configurado.
- [ ] Revisar acessibilidade com leitor de tela e teclado físico.

## Evidências verificáveis
- Primeiro teste de APK e tema aprovado: https://github.com/nego001/ReaDroid-Native/actions/runs/39183969729
- Builds Android e verificações de código aprovados até `e7830d7c`.
- Teste estendido de APK, OLED → Claro, fontes a 130% e modo compacto aprovado: https://github.com/nego001/ReaDroid-Native/actions/runs/39184741134
- Build Android e Source checks aprovados no commit `bfdc8717`.

Este trabalho fica numa branch de desenvolvimento, separado do lançamento
`v3.0.0-preview.1` e de futuras versões definitivas.
