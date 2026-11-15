# P7.36.2 — Reinício controlado da API35 antes da captura compacta

## Evidências da falha após sucesso integral nos testes
Na [matriz P7.36.1 #40103796487](https://github.com/nego001/ReaDroid-Native/actions/runs/40103796487), Android 10/API29 terminou **success** com 14 PNGs. Android 15/API35 concluiu com **success em TODAS as três sessões de instrumentação**: 1/1, 36/36 e 116/116, totalizando **153/153 testes sem falha/skip**. A captura normal de Home, Explorador, Segurança, Build, Design, Ícones e Logotipo também passou.

A falha ocorreu **depois**, em `tools/p7_compact_smoke.py`:
- `P7_COMPACT_START api=35 original=(1080, 2220) compact=(880, 1980) density=440 original_font=1.0`.
- Após aplicar `wm size` e `font_scale=1.3`, `adb shell am start -W -n com.readroid.app/.MainActivity` ultrapassou **45 segundos**, seguido de `error: closed`, `TimeoutExpired` e desconexão ADB.
- O script tentou restaurar `wm size` no `finally`, mas a conexão já havia sido perdida; nenhuma alegação de recuperação.
- O artefato contém **8 PNGs de 14 previstos**, e o XML da última sessão confirma 116 testes, sem falha. Cross-review corretamente `skipped`.
- Não há asserção comprovando crash da aplicação. A causa ambiental da desconexão após a mudança de resolução ainda não está encerrada.

## Mitigação operacional sem relaxamento de gates
- Manter a execução integral das **três sessões obrigatórias e todos os 153 testes** por API, e as capturas normais antes da alteração.
- **Somente na API35**, entre o screenshot normal do Logo Studio e o início de `p7_compact_smoke.py`, fazer `adb reboot` no **mesmo emulador e com o mesmo APK debug**. Não reinstalar outro APK, não criar screenshots artificiais e não executar testes reduzidos.
- Esperar até 150s pela reconexão ADB, no máximo 60 verificações de boot (2s cada), exigir `sys.boot_completed=1`, pacote realmente presente, resolução e densidade reais acessíveis. Qualquer falha na reinicialização aborta o job por `set -eu`.
- Depois executar o `p7_compact_smoke.py` original com **320 dp/130%** em três telas, restaurar display e executar `p7_large_text_smoke.py` original com **200%** e screenshot nas mesmas três telas. Não diminuir os alvos mínimos de 48dp, verificar foco e overlays, nem aceitar screenshots incompletos.
- Atualizar o contrato `tests/test_p7_capture_runner.py` para obrigar a ordenação reboot/prova de boot/pacote/captura compacta e preservar o inventário. Sem alterações no Android Java, SAF, ZIP, APK/OTA ou preferências persistidas.

**É uma mitigação para investigar estabilidade, não prova de causa raiz.** Se a API35 voltar a desaparecer no resize mesmo após reboot, investigar o ambiente AVD/Swiftshader ou criar um job separado de evidência sem enfraquecer a suíte, e registrar a ocorrência.

## Gates
- [ ] Source checks/OTA do novo HEAD.
- [ ] Android10/15 com todas as sessões 1+36+116 e 14 PNG por API.
- [ ] Cross-review 28/28.
- [ ] Galaxy A55/TalkBack e fidelidade visual 1:1 continuam pendentes.

PR #13 draft; `main` intacta, sem merge nem APK de distribuição ou OTA publicada; `visual_1to1=NOT_APPROVED`, `physical=NOT_APPROVED`.
