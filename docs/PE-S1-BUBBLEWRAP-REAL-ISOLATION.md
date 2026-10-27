# NegrescoDroid | PE-S1: teste de isolamento real Bubblewrap com Ghidra

## Escopo

Este ramo empilha-se sobre a PE-A4.4 (PR #46) para sair dos antigos **testes apenas de construção de argumentos** do Bubblewrap. O novo workflow `pe-ghidra-sandbox-real.yml` executa um probe dentro do namespace e tenta a análise Ghidra Headless **sem a opção que desativa isolamento**, com PE Windows sintético e inofensivo compilado na CI. O executável Windows é analisado como dados, nunca executado.

## Perfil com JDK fixado

`tools/pe_ghidra_sandbox.py` trata duas instalações confiáveis de Java: um `JAVA_HOME` sob `/usr` fica disponível pelo runtime já montado somente leitura; quando Java está instalado fora de `/usr` (por exemplo JDK 25 do GitHub Actions), apenas o diretório apontado por `JAVA_HOME` é montado em `/opt/negresco-jdk` **somente leitura**, sem disponibilizar todo `/opt`, `HOME` ou a árvore do runner. O `PATH` dentro do namespace privilegia `JAVA_HOME/bin`. Instalações ausentes ou sobrepostas ao Ghidra são rejeitadas.

## Provas funcionais incluídas

O arquivo `tests/pe_sandbox_probe.py`, executado **dentro** do exato prefixo Bubblewrap usado para Ghidra, verifica:

- namespace de rede diferente daquele do processo host;
- arquivo-sentinela previamente criado no `$HOME` do runner ausente dentro do namespace;
- ausência de `/etc/passwd` do host e diretório `/home` isolado;
- montagem do runtime `/usr` em modo somente leitura;
- acesso somente ao Ghidra e ao JDK fixados, com `HOME` redirecionado para `/work`;
- capacidade de escrita **apenas no workspace temporário permitido**.

O teste compara o namespace de rede e visibilidade, sem tentar acessar serviços externos. Depois a CI faz uma análise real PE no Ghidra dentro do mesmo perfil padrão e exige metadados, pseudocódigo, string-sentinela e hipótese estática WinAPI. Se Bubblewrap não conseguir estabelecer o namespace, **o teste falha sem desativar AppArmor, mudar sysctl, usar root no analisador ou executar Ghidra sem sandbox**.

## Ambiente e limites

A primeira matriz usa um runner Ubuntu 22.04 efêmero, Bubblewrap do sistema, Ghidra 12.2 oficial com SHA-256 fixado e JDK 25. **Isso não comprova Arch Linux + Hyprland, KDE ou GNOME**, nem representa uma VM. O isolamento de diretórios e rede por namespaces não substitui limites rígidos de recursos, filtros seccomp, auditoria de vazamento de descritores de arquivo, verificação de kernel/LSM ou revisão de vulnerabilidades do Ghidra. Não declarar seguro para executáveis hostis até uma matriz com kernel/distribuição e política de isolamento adequadas.

Ubuntu 24.04 pode impor restrições AppArmor a namespaces de usuários. Um resultado `Operation not permitted` deve ser relatado como ambiente indisponível, **não como aprovação** ou convite para desabilitar a segurança do host.

Os resultados só podem ser chamados de homologados depois que **o probe funcional e o Ghidra real** passarem no mesmo SHA da PR, juntamente com Source checks/OTA/PE. O IObit Uninstaller real segue não analisado; fluxo de selecionar `.exe` na interface ainda não existe. PR em Draft, sem merge em `main` nem APK/OTA publicados.