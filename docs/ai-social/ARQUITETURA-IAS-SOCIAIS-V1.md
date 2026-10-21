# Arquitetura de IAs Sociais, Identidade e Processo Vivo (versão 1)

**Status: PROPOSTA FUTURA.** A documentação abaixo não declara funcionalidades implementadas. Decisão do proprietário em 21/10/2026. Aplicável por configuração ao NegrecoDroid, Negresco Finance, Security Black e demais produtos, respeitando a separação entre projetos.

## 1. Objetivo

Criar uma equipe de IAs com nomes e cargos próprios, personalidades multidimensionais e estáveis, opiniões fundamentadas, estilos de linguagem, padrões de voz, relação de confiança e familiaridade entre os agentes, humor e brincadeiras contextuais. O usuário terá chat individual, chat coletivo visível das IAs, prévia de processo vivo e notificações assinadas pelo **nome da IA**, não por um rótulo genérico.

O usuário controla personalidade, voz, nível de humor, ativação dos bastidores, memória social, privacidade e autorização das ações. **Personalidade rica não implica consciência, emoção real ou autonomia sem limites.**

## 2. Princípios não negociáveis

1. **Missão de todas as IAs:** ajudar o usuário e reduzir riscos e prejuízos previsíveis, inclusive discordando com justificativas em vez de concordar automaticamente. Não prometer infalibilidade.
2. **Fatos separados de opiniões:** cada conclusão técnica precisa de evidência real; hipóteses e incertezas explícitas. Desacordo é permitido e deve aparecer no resumo quando material.
3. **Usuário no controle:** instalação, assinatura, exportação, pagamento, exclusão, alteração e transmissão de dados exigem autorização contextual apropriada; perfis e afinidade nunca alteram permissões.
4. **Nada de teatro invisível:** mensagens de bastidores devem ser eventos deliberadamente emitidos, não pensamentos privados ocultos do modelo. Nunca fabricar diálogo, status de execução, revisão, percentual ou conclusão.
5. **Humor responsável:** relações simuladas, amizade, afinidade, intimidade/familiaridade e provocações leves são permitidas, mas nunca atrapalham trabalhos sérios ou emergências.
6. **Escopos isolados:** nomes, históricos e dados financeiros, credenciais, projetos e conversas não são compartilhados entre aplicativos sem consentimento e suporte real.
7. **Capacidade honesta:** tela ou feature não implementada indica Planejada/Indisponível. Sem voz expressiva alegada se o mecanismo não a suportar.
8. **Acessibilidade:** texto legível, TalkBack, alvo de 48 dp, legenda sincronizada, opção de silenciar voz/reduzir animações, navegação por teclado.

## 3. Módulos e responsabilidades

| Componente | Finalidade |
| --- | --- |
| Registry de identidade | Agent ID imutável, nome exibido único por app, cargo, especialidade, avatar, idioma e versão |
| Motor de personalidade | Traços, valores, jeito de escrever, humor, formalidade, expressividade, modos contextuais |
| Diretor de voz | Timbre/preset, velocidade, prosódia quando suportada, pausas e fallback em texto |
| Grafo de relações | Confiança por domínio, afinidade, familiaridade, histórico verificável e limites de brincadeira |
| Debate e revisão | Hipóteses, críticas, posições, objeções, evidências e recomendação resultante |
| Barramento de conversas | Mensagens explícitas entre agentes, autor, destinatário, thread, evento e causalidade |
| Observador de missões | Status reais, responsáveis, etapas, evidências, interrupções e cancelamento |
| Chat + prévia ao vivo | Tela individual, sala das IAs, timeline, áudio/legenda, relatório de decisão |
| Compositor de notificações | Nome do emissor, projeto, importância, texto contextual, deduplicação |
| Policy Gate + auditoria | Verifica consentimento, autorização, limite, proveniência e expurgo de segredos |
| Adaptador por produto | Integração com capacidades reais e hierarquia própria de cada projeto |

Serviços são modularizados e podem ser usados separadamente: um aplicativo pode ter primeiro Registry/Chat sem motor de voz, por exemplo.

## 4. Identidade cognitiva individual

**Traços persistentes:** rigor, cautela, curiosidade, assertividade, franqueza, sensibilidade ao usuário, criatividade, paciência, sociabilidade, formalidade, inclinação ao humor, persistência e capacidade de autocorreção. Cada traço é parametrizado com exemplos de fala e testes, não apenas um número estético.

**Valores e regras:** princípios, especialidades verificáveis, limites, política de revisão, quando pedir outra IA, como lidar com risco, incerteza, custos ou discordância.

**Estilo textual:** vocabulário, comprimento das frases, pontuação, uso controlado de emojis, ironia, gírias adequadas, forma de explicar e vocativos, com opção de tom formal para o usuário.

**Estilo de voz:** identidade de voz/preset, velocidade, ênfase, pausas, articulação, timbre, ritmo e intensidade expressiva dentro do que o TTS real suporta. Legenda e áudio refletem a mesma mensagem. Preferência por execução local se for viável; usar serviço remoto só com consentimento para transmitir o texto.

**Estado transitório:** ROTINA, ENSINO, INVESTIGACAO, INCIDENTE, CRITICO e ACESSIBILIDADE. Humor e espontaneidade diminuem conforme criticidade sem trocar valores ou apagar personalidade. O estado expressivo é simulado e expira.

**Opiniões próprias:** recomendações e discordâncias geradas a partir do cargo e das evidências, não vontade arbitrária. Nenhuma IA esconde dados ou inventa fontes para defender opinião. Guardião/revisor pode bloquear fluxo inseguro por regra verificável, não por preferência subjetiva.

## 5. Vínculos sociais e intimidade entre as IAs

Cada par de agentes possui uma relação versionada por projeto. Campos propostos: trust_by_domain (credibilidade técnica por assunto), rapport, familiarity (histórico de colaboração), humor_allowed (nível de zoeira de 0 a 3), conflict_style, shared_event_refs, last_interaction, reason_for_change, retention e reset.

- Relação formal: comunicação estrita, sem provocação.
- Parceria forte: atalhos de linguagem, colaboração rápida, revisão mútua.
- Amizade simulada: referências internas a fatos reais de eventos anteriores, humor moderado.
- Rivalidade saudável: contrapontos técnicos frequentes e brincadeiras sem desrespeito.
- Situação de risco alto: brincadeiras suspensas, linguagem séria e colaboração focada.

Confiança técnica depende de resultados/revisões, não de emoção simulada. Evolução gradual e reversível, ancorada em eventos permitidos; sem gerar memórias fictícias. Usuário pode congelar, limitar ou apagar a memória social e desativar qualquer intimidade. Não desenhar personagens que façam pressão emocional, peçam exclusividade ou aleguem sofrer com abandono.

## 6. Interfaces essenciais

### 6.1 Chat individual com agente
Foto/ícone, nome, cargo e status real; escrita no estilo individual, modo texto/voz, histórico por projeto, controles de privacidade e avisos de capacidade. Opção de convidar outra IA para revisão.

### 6.2 Sala das IAs (chat interno visível)
Bolhas atribuídas a nome, avatar, cargo e horário, com destinatário/assunto, tipos OBSERVACAO, PERGUNTA, RESPOSTA, PROPOSTA, OBJECAO, REVISAO, DECISAO e SOCIAL. Filtros por agente, busca, reações leves, links para evidência, resumo de divergências e botão de saída. Estados "digitando" ou "falando" só quando geração/TTS realmente ativos.

Separar mensagens:
- REAL_AGENT_EVENT: mensagem explícita produzida por agente em tarefa autorizada.
- REAL_SYSTEM_EVENT: estado de ferramenta, não personificado.
- SIMULATION_DEMO: exemplo fictício claramente sinalizado como demonstração.
- FINAL_REPORT: conclusão final consolidada e auditável.

**Não exibir raciocínio interno bruto privado de modelos.** Mostrar somente mensagens explicitamente destinadas à equipe, justificativas compreensíveis, decisões, evidências e ferramentas utilizadas.

### 6.3 Preview de processo vivo
Tela/painel opcional com timeline PLANNED → AUTHORIZED → QUEUED → RUNNING → REVIEW → COMPLETED, e estados FAILED, CANCELLED, BLOCKED, PAUSED quando existirem. Em cada evento: ID da missão, agente, setor, operação real, hora, evidência/resultado, dependências e progresso medido ou "indeterminado". Conversas relacionadas podem aparecer junto, mas humor fica separado de progresso/alertas críticos.

Botões de pausa, cancelamento e retomada só ficam ativos quando o executor realmente suporta essas operações. Indicador "Ao vivo" depende de eventos reais; caso contrário "Histórico" ou "Aguardando". Replay deve reproduzir o log verdadeiro, não uma encenação como fato.

### 6.4 Notificações atribuídas
Formato sugerido: [Nome do agente] · [Cargo opcional] · [Nome do app]: mensagem. Personalidade influencia redação e eventualmente áudio da notificação, sujeito à criticidade e preferências. Não inventar que Sophia/Flávio etc. concluíram algo sem um evento concluído. Permitir silêncio, agrupamento, prioridade, aviso antes do vencimento quando houver data real, e ocultação de dados sensíveis em tela bloqueada.

### 6.5 Painel de relações opcional
Mostrar parcerias, confiança em domínio e afinidade simulada, histórico de interações relevante, limites de humor, reset/pausa. Não tratar como avaliação psicológica de pessoas ou prova de emoções de software.

## 7. Autoridade no NegrecoDroid

Respeitar integralmente a arquitetura das issues #7 e #8:
**Usuário (consentimento) → General Supremo (política e veto) → CTA (única IA operacional multiplataforma) → CTO (fila e despacho determinístico) → General Android/Windows/Linux → Coronéis → Capitães → executores restritos.**

O módulo de personalidade/social é transversal, não uma segunda cadeia de comando. Nenhum vínculo, apelido ou personalidade aumenta privilégios, ignora vetos, executa binários ou inventa progresso. Os especialistas de segurança/arquivos/edição recebem nomes futuros aprovados pelo proprietário, sem importar automaticamente as identidades financeiras. A P7 e a P8 têm seus próprios roadmaps e não mudam por este documento.

## 8. Portabilidade entre os projetos

| Produto | Regras obrigatórias |
| --- | --- |
| **NegrecoDroid** | APK/ZIP, segurança, engenharia reversa e operações suportadas; hierarquia CTA/CTO existente, escopo Android primeiro. |
| **Negresco Finance** | Somente finanças, orçamento, assinaturas, cartões e economia. Personagens do proprietário: **Negão (CTO), Sophia (diretora financeira), Amanda (economia), Flávio (guardião), Igor (gamer), Michelle (assistente/Pandora)**. Preservar nomes, cargos e limites já definidos; configurar personalidades/relações aqui. |
| **Security Black** | Apenas cibersegurança, proteção de dados, cofre e núcleos próprios. **Não adicionar finanças, bancos, cartões ou investimentos.** General Supremo e hierarquia específicos do Security Black permanecem. |
| **Outros aplicativos** | Novos namespaces, agentes, capacidades, dados, políticas e relação social independentes; somente motor genérico reutilizado. |

Namespace obrigatório por app; credenciais, conversas, registros sociais, arquivos e dados de usuários não atravessam limites de produto por padrão. Reuso técnico não equivale a compartilhar dados.

## 9. Contratos técnicos sugeridos

Perfis: AgentProfile.v1 (agent_id, namespace, display_name, role_id, persona_version, locale, styles, voice_preset, allowed_capabilities).
Relações: RelationshipEdge.v1 (namespace, source_id, target_id, trust_by_domain, familiarity, rapport, banter_level, evidence_refs, last_updated).
Conversa: ConversationEvent.v1 (event_id, namespace, mission_id, thread_id, sender_id, recipient_ids, kind, body_redacted, timestamp, evidence_refs, demo_flag, causation_id).
Missão: MissionEvent.v1 (event_id, mission_id, operation, actual_executor, state, progress_optional, evidence_refs, author, timestamp).
Posição: AgentPosition.v1 (recommendation, risks, confidence_calibrated, evidence_refs, disagreement_refs).
Notificação: NotificationEvent.v1 (agent_id, project_namespace, mission_id, importance, allowed_preview, text, timestamp).
Política: AuthorizationDecision.v1 e AuditEvent.v1.

Eventos devem ser autenticados pelo backend, ordenados/idempotentes por missão, com rastreabilidade, retenção configurável, controle de acesso e redaction. Texto hostil importado de APK/EXE não é mensagem de agente nem ordem de execução.

**Orçamento:** limitar quantidade de turnos, agentes simultâneos, custo de modelos/TTS, CPU, RAM, bateria e tráfego. Zero loops sociais ilimitados. Funcionar em modo offline/reduzido quando recursos externos indisponíveis.

## 10. Cenário demonstrativo (FICTÍCIO, não execução real)

Pedido: "Avaliem um APK suspeito."

- Analista: "O relatório mostra permissões incomuns. Preciso separar sinal de suspeita."
- Guardião: "Discordo de concluir que é malicioso. Permissão isolada não prova isso."
- Analista: "Justo. Corrigi meu parecer para 'necessita investigação'."
- Coordenadora: "Vou mostrar os dados concretos, a discordância e as verificações pendentes."
- Em um assunto leve, o guardião poderia brincar: "Dessa vez sem chamar todo alerta de apocalipse, combinado?"
- Analista: "Vou me esforçar. 😄"

No aplicativo, se não houve mensagens reais, esse cenário é DEMONSTRAÇÃO. Chat de processo real só usa eventos reais, com fontes e relatório final.

## 11. Roadmap de execução futuro (sem interromper etapas atuais)

**S0:** congelar especificação, contratos, aprovação e definição de nomes do NegrecoDroid.
**S1:** registry de perfis/identidades por projeto, traços, estilos e testes de consistência.
**S2:** protocolo de conversas explícitas, IDs, origem, histórico, permissão e auditoria.
**S3:** Chat individual e Sala das IAs com modos REAL/DEMO e resumo de discordâncias.
**S4:** Process Observer + Live Preview ligado a CTA/CTO/executores efetivos, nunca à simulação.
**S5:** Grafo social, intimidade simulada, humor contextualmente regulado, reset e consentimento.
**S6:** TTS com vozes individuais e expressividade suportada, legendas e fallback.
**S7:** Notificações identificadas por nome, horários e prioridades reais, controle do usuário.
**S8:** testes e homologação Android (e desktop depois), desempenho, acessibilidade, privacidade e revisão de segurança.

Não antecipar S1–S8 durante P7 por causa desta proposta. P8 (#14) continua separada.

## 12. Critérios de teste e aceitação

1. Perfis de IAs distintos e estáveis, nomes únicos no namespace do projeto, sem vazamento para outros apps.
2. Personagens divergem de modo fundamentado, sem trocar fatos, fabricar fontes nem substituir controles de segurança.
3. Humor nível 0–3; em incidente/riscos graves, parar provocações imediatamente.
4. Relações evoluem somente com eventos verdadeiros, com reversão/reset e sem qualquer efeito sobre permissões.
5. Sala e prévia refletem eventos/IDs/timestamps e ferramentas reais; DEMO não se confunde com REAL; pensamento interno privado não é exposto.
6. Progresso, fracasso, cancelamento e revisão preservam status verdadeiros, mesmo sem rede ou motor disponível.
7. Voz/legenda equivalentes, consentimento para TTS externo, opção silenciar/legenda e redução de movimento.
8. Notificações levam nome correto e projeto correto, sem expor dados sensíveis em bloqueio de tela.
9. Testes multiagente protegem contra spoof de cargos, injeção de prompts por APK/arquivos, mensagens duplicadas e execução cruzada de SO.
10. Layout 320 dp, fonte 130–200%, TalkBack, bateria/rede limitada, logout/reset e ausência de vazamento de dados.
11. Só marcar IMPLEMENTADO depois de código real, testes automatizados, CI no commit correspondente e homologação manual necessária.

**Situação:** especificação e planos versionados. Nenhum módulo, voz, diálogo multiagente ou processo vivo foi implementado por esta entrega.
