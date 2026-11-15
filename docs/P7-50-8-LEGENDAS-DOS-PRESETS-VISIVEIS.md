# P7.50.8 — legendas dos cinco presets acima da navegação

**Origem:** comparação visual entre a referência oficial `design/reference/p7/negrecodroid_controle_total_de_apks.png` e o PNG real `p7-design-android-29.png` do commit P7.50.6. Na captura real, os presets aparecem na parte de baixo e suas legendas são parcialmente cobertas pela barra de navegação. A P7.50.7 melhora a largura para cinco cartões, mas a checagem `require_five_preset_previews` valida apenas posição horizontal e limites da tela. Isso não basta para declarar legibilidade da primeira dobra.

## Correção em staging

- Para o **viewport de referência 390 a 419 dp em escala de texto efetiva até 115%**, reduz ligeiramente as miniaturas de temas de 74 para 70 dp, layout de 57 para 53 dp e presets de 46 para 41 dp; são as mesmas views nativas, mesmo `P7ThemePreviewView`, sem alterar a relação de cores/temas.
- Os dois cartões `Criador de Ícones` e `Logo Studio` continuam clicáveis com seus desenhos vetoriais originais e mesma descrição TalkBack; apenas o espaçamento superior/inferior de cada um passa de 12 para 8 dp e sua altura mínima de 88 para 80 dp no mesmo viewport. O cálculo economiza espaço **sem remover seção ou elemento** e sem sacrificar alvos de toque de 48 dp.
- Em **320 dp**, fonte de 130/200%, tablets e outras configurações, mantém as dimensões anteriores. O layout continua verticalmente rolável para quem precisa.
- Novo gate real `require_preset_labels_above_bottom_nav` exige que os cinco cartões interativos estejam **inteiros acima do limite superior da barra inferior** no viewport padrão (usando as coordenadas `bounds` capturadas do Android), deixando ainda uma folga real de pelo menos 1 dp. Não é um teste baseado em desenho ilustrativo. Simulações negativas incluem sobreposição real, toque de bordas, barra adiantada, geometria inválida e ausência do quinto.
- Teste instrumentado de política já existente verifica os tamanhos relativos em telefones padrão, estreitos, tablets e fonte ampliada, sem adicionar testes `@Test` nem modificar os 47 testes de navegação.

## Critérios de aprovação

Meta preservada de **170 instrumentados/API**, Android 10/15, 14 capturas por API, cross 28/28, 320dp/130%, 200%, reboot API35 e Source/OTA; todas as capturas devem ser reais e todos os novos gates de geometria verdes no mesmo SHA. O PNG da tela do Design deverá ser revisado para confirmar que os nomes Dark OLED, Cyber Neon, Minimal, Glass e Retro aparecem de fato.

**Status:** somente staging, sobre a P7.50.7 `093cc6c6` ainda em CI. Não integrar enquanto a matriz da P7.50.7 estiver pendente. PR #13 draft, `main` intacta, nenhum APK/OTA publicado. Revisão humana 1:1 e Galaxy A55/TalkBack físico continuam pendentes.
