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
- [x] OTA mantém avisos verdadeiros sobre configuração incompleta e sem instalação automática.
- [x] Navegação inferior com seleção visual em cartões e descrições acessíveis.
- [x] Ajuste de contraste WCAG nos botões, aviso para cor HEX pouco legível.
- [x] Resumo do projeto reduzido; dados técnicos completos permanecem no relatório.
- [x] Troca de tema/rotação retêm APK, relatório e plano textual na mesma sessão.
- [x] Recuperação do arquivo selecionado quando a análise é interrompida pela recriação da Activity.
- [x] Estado aberto/fechado do painel de personalização persistido separadamente.
- [x] Teste manual de emulador preparado: abertura, troca de abas e captura da tela.

## Restrições
- **Não** criar funcionalidades de assinatura APK que o programa ainda não suporta.
- **Não** alterar certificado de APK, chaves, análise de segurança nem as permissões Android.
- Mudanças visuais devem preservar controles, callbacks e resultados técnicos.
- Preferências personalizadas devem continuar funcionando nos temas claro e grafite.
- Nenhuma versão final V3 deve ser publicada automaticamente.
- A arte referência tem brilhos e detalhes decorativos que foram reinterpretados com
  gradientes e desenho vetorial, para evitar consumo excessivo de GPU/CPU.

## Validação
- [x] Builds Android intermediários concluídos com sucesso na branch.\n- [ ] Confirmar compilação Android após o último commit.
- [ ] Executar o workflow manual `V3 Android UI smoke` na branch `feature/v3-design-studio`, verificar a captura e eventuais erros de execução.\n- [ ] Abrir em celular físico, tocar em todas as opções e conferir rolagem/áreas de toque.
- [ ] Testar seleção real de APK, exploração de arquivos, relatório e exportação.
- [ ] Conferir tema claro, fonte a 130%, modo compacto e largura de 320–360 dp.
- [ ] Testar importação de presets anteriores e do novo conjunto.
- [ ] Confirmar que o código OTA permanece bloqueado quando não configurado.
- [ ] Revisar acessibilidade com leitor de tela e teclado físico.

Este trabalho fica numa branch de desenvolvimento, separado do lançamento
`v3.0.0-preview.1` e de futuras versões definitivas.
