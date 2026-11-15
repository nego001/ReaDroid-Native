# P7.36.4 | Reboot isolado em um único script Bash

[P7.36.2 #40105068417](https://github.com/nego001/ReaDroid-Native/actions/runs/40105068417) falhou no Android10 após todas as 153 instrumentações e os smokes normais: `/usr/bin/sh: Syntax error: end of file unexpected (expecting "fi")`. O executor de emulador processa cada linha `script` como comando independente; portanto o `if/fi` inline não funciona. Na API35 houve queda de emulador durante o teste de welcome-card com fonte 135%, antes do reboot. Nenhuma das falhas demonstra defeito do aplicativo.

O workflow chama uma linha única `bash tools/p7_api35_reboot.sh ${{ matrix.api }}`, após a captura de logo e antes da compacta. Dentro do script: `set -euo pipefail`, API29 retorna sem reiniciar, API35 faz `adb reboot`, exige reconexão em até 150s, boot concluído, pacote instalado, dimensão e densidade válidas. APIs desconhecidas e todas as falhas bloqueiam. `bash -n` é gate obrigatório; contrato Python analisa o script. Não instala nada, não altera código Android, não remove testes nem imagens.

A etapa P7.36.3 também isola integralmente o teste de welcome-card fonte 135%, que provocou o novo desaparecimento do emulador API35. As quatro sessões passam a ser 1+1+35+116, **153 testes em cada API**, antes dos smokes. Mantidos 320dp/130%, 200%, 14 capturas por API e cross-review 28/28.

Pendente: CI verde completa e homologação humana do Galaxy A55/TalkBack e visual 1:1. PR #13 draft, sem merge `main`, sem APK/OTA publicada.
