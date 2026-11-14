# PE-S2.52 | Hora UTC canônica entre produtor, captura e revisão (HOLD)

## Inconsistência de contrato

Os produtores S1.70 e S1.71 escrevem `observed_utc_untrusted` usando `datetime.now(timezone.utc).isoformat()`: calendário `YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00`. Entretanto, os consumidores S1.71 e S1.73 aceitavam qualquer data UTC que `datetime.fromisoformat()` entendesse, inclusive formatos que o produtor **nunca** emite: semana ISO (`2026-W45-1T...`), separador de espaço, sufixo `Z` e fração de segundo abreviada. Um SHA-256 externo correto fixa bytes, não atesta que o envelope tem a forma esperada.

Isso podia produzir uma revisão offline com estado HOLD localmente coerente para um registro re-hasheado fora do contrato do produtor. Não significa que o horário reportado era real ou autenticado.

## Medida

- Adicionado `host._validate_untrusted_utc_isoformat(value)`, que exige string exata, tamanho máximo 50, data/hora válida, deslocamento UTC zero e igualdade byte textual à reconstrução `datetime.fromisoformat(value).isoformat()`.
- S1.71 reutiliza a função para rejeitar o primeiro log S1.70 **antes** de consultar `virsh` ou o guest agent.
- S1.73 reutiliza a mesma função para os horários dos dois registros, após verificar os SHA-256 externos. Continua invocando primeiro o validador integral S1.71 do registro do host.
- `2026-11-02T16:00:00+00:00` e `2026-11-02T16:00:00.123456+00:00` são canônicos. `Z`, espaços, datas por semana, frações abreviadas, `.000000` supérfluo e fusos não UTC são rejeitados.
- A checagem é **apenas de sintaxe**. Não certifica relógio sincronizado, ordem cronológica real, host, VM ou independência de custódia.

## Regressões

Quatro novos métodos: validador direto com casos válidos/inválidos, S1.71 com snapshot S1.70 forjado e repinado que deve falhar antes de qualquer `virsh`, S1.73 com ambos os hashes reconstruídos e vínculo host/guest atualizado, e S1.73 com horário somente do segundo registro forjado e hash correspondente recalculado. Os testes são inteiramente sintéticos.

O status de êxito local permanece **HOLD**. A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) segue Draft/unmerged e a [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) segue OPEN. Revisor independente com host QEMU/libvirt e VM Arch nativa continua obrigatório para PID Ghidra, cotas cgroup v2/seccomp, journald, cleanup e cronologia testemunhada BEFORE → WORK → AFTER. Sem merge, execução de Windows PE desconhecido, APK, OTA ou release.
