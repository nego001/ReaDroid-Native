# P7.38 — testar comportamento do reboot Android 15 com ADB simulado

Depois da matriz verde P7.36.4, verificar **com execução** que `tools/p7_api35_reboot.sh` realmente bloqueia estados inseguros. A checagem anterior inspecionava só o texto do script, não seu comportamento em falhas.

## Nova regressão: 9 casos
`tests/test_p7_api35_reboot.py` invoca o Bash real com ADB simulado e verifica:
- Android 10/API29 retorna sem reboot nem contato ADB; API não suportada é recusada.
- Android 15/API35 com boot saudável exige, nessa ordem, reboot, reconexão, conclusão do boot, mesmo pacote instalado, dimensões e densidade, sem instalar APK diferente.
- Falha do reboot, falha ADB, boot incompleto, pacote ausente, tamanho inválido ou densidade inválida devolvem código não zero, antes da captura compacta.
- Na simulação do boot incompleto, `seq` é reduzido **somente no subprocesso simulado** a três tentativas para manter o teste rápido; o script real **continua com 60 verificações**.
- A nova suíte roda no preflight do workflow P7 com `python3 -m unittest discover -s tests -p 'test_p7_api35_reboot.py' -v`.

## Status
Nove testes passaram localmente em ambiente isolado; não provam estabilidade do emulador real. Integrar à PR #13 apenas após aprovação completa da matriz P7.37, sem remover instrumentação ou captura. Continua obrigatório: 154 testes/API, 14 PNGs/API e 28/28 na revisão cruzada. Sem alteração do app Android de produção, publicação APK/OTA ou aceite visual/telefone físico.
