# NegrescoDroid | PE-A2.1: Ghidra real e isolamento obrigatório para arquivos desconhecidos

**Base:** PE-A2.1, PR #38, execução comprovada do Ghidra 12.2 em Linux. Este ramo adiciona um perfil de proteção Bubblewrap experimental, sem alterar `main` nem publicar APK.

## Evidência de integração real

A [CI Ghidra real #40409098283](https://github.com/nego001/ReaDroid-Native/actions/runs/40409098283) executou o Ghidra 12.2 oficial com JDK 25, após conferir SHA-256 do pacote `2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67`. Usou um executável PE32+ sintético compilado pela própria CI, sem executar o código Windows: **109 funções reconhecidas, 78 exportadas** para a prévia. Os testes Python da PE-A0, A1 e A2 permaneceram aprovados.

A integração real e a construção do **perfil Bubblewrap** são duas capacidades diferentes: a primeira foi testada end-to-end; a segunda tem **somente testes de contrato e simulação** nesta etapa. Não confundir os resultados.

## Proteção PE-A2.1 adicionada

`tools/pe_ghidra_sandbox.py` prepara um comando Bubblewrap para executar Ghidra em um namespace Linux com:

- `--unshare-all`: namespaces separados, incluindo isolamento de rede;
- `--die-with-parent` e `--new-session`: controle de vida do processo;
- sistema runtime `/usr` visível **apenas leitura**, com links ou binds mínimos para `/bin`, `/lib`, `/lib64` e `/sbin` quando existirem;
- instalação Ghidra somente leitura em `/opt/negresco-ghidra`;
- apenas uma pasta de trabalho temporária em `/work`, montada em leitura/escrita, contendo cópia do PE, projeto e script exportador;
- `/tmp` e `/home` isolados, `/proc` e `/dev` preparados no namespace; variáveis HOME/PATH/cache redefinidas;
- recusa de execução como root, diretórios que se sobrepõem e instalação/scripts ausentes.

O executor `tools/pe_auto_ghidra.py` agora usa **Bubblewrap por padrão**. Se o host não tiver `bwrap`, usuário namespaces ou outros pré-requisitos, a análise deverá **falhar fechada** e não produzir relatório aceito. Não há fallback silencioso para executar em ambiente desprotegido.

## Testes automáticos

`tests/test_pe_ghidra_sandbox.py` verifica montagem pretendida e opções de namespace **sem executar o Bubblewrap**. `tests/test_pe_auto_ghidra.py` preserva os mocks antigos, marca explicitamente seus arquivos como fixtures confiáveis e comprova recusa por falta de Bubblewrap no fluxo padrão.

Os testes não comprovam proteção contra escapes de namespace, vulnerabilidades do kernel nem compatibilidade com todas as instalações reais do Ghidra. **Arquivos Windows potencialmente maliciosos ainda devem ser analisados numa VM descartável** enquanto não existir CI de sandbox funcional com kernel alvo e políticas verificadas.

## Teste sem sandbox permitido só para fixtures confiáveis

`--allow-unisolated-synthetic-fixture` serve à **CI, que compila seu próprio PE sintético** para testar integração real do Ghidra. Essa opção desativa o perfil Bubblewrap explicitamente e o relatório declara `os_sandbox=not_implemented`. Não é a opção normal do produto e não deve ser empregada com arquivos baixados ou desconhecidos.

O modo normal usa:

```bash
python3 tools/pe_auto_ghidra.py /caminho/componente.exe \
  --ghidra-home /caminho/ghidra_12.2_PUBLIC \
  --output /caminho/resultado.json
```

Necessita Bubblewrap, Ghidra e JDK compatível em Arch Linux e que o sistema suporte namespaces de usuário. O comando acima é uma interface técnica de desenvolvimento; o fluxo *um clique* ainda não foi construído.

## Limites que permanecem

- O Ghidra analisa os arquivos como dados. **Não executamos o PE Windows**, mas o analisador e os scripts Java são processos reais e podem ter bugs.
- O perfil Bubblewrap é uma camada de isolamento, **não uma VM** nem garantia de segurança perfeita.
- A CI com Ghidra real usou somente uma fixture inofensiva e **não testou o IObit Uninstaller**.
- O programa ainda não reconstrói pseudocódigo, call graph, comportamento, arquitetura interna completa nem os componentes embalados num instalador.
- Suporte real Windows no PC e a interface Android/PC de um clique ainda não estão disponíveis.

## Critérios pendentes

Validar o comando Bubblewrap real num Linux com JDK25 instalado em `/usr`, incluindo impossibilidade de leitura de `$HOME` do host e acesso à rede; medir limites de RAM e CPU sob carga; validar um corpus PE não proprietário. Até lá, os resultados dos testes de contrato não equivalem à homologação do isolamento.

Referências:
- https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.2_build
- https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md
