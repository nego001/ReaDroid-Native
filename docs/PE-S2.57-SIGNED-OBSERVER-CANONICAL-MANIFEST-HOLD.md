# PE-S2.57 | Contrato canônico do manifesto externo assinado (HOLD)

## Divergência entre produtor e consumidor

O produtor S1.65 cria `external-observer-manifest.json` usando `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\\n"`. A data `observer_local_time_utc_not_attested` é produzida por `datetime.now(timezone.utc).isoformat()`.

O consumidor S1.63 validava estrutura, pins, hashes e assinatura Ed25519, porém não exigia o JSON textual exato do produtor. Também usava apenas `datetime.fromisoformat()` no horário: aceitava `Z`, espaço no lugar do `T`, semana ISO e microssegundos abreviados. Assim, um manifesto alternativo re-assinado por quem detenha uma chave de assinatura podia ultrapassar o gate sintático, apesar de não ter o formato escrito por S1.65.

**Importante:** assinatura válida autentica os bytes sob a chave verificada, não a origem independente das informações, a fidelidade do relógio nem o host/VM real.

## Endurecimento

- S1.63 exige igualdade literal com seu serializador `_canonical_manifest`, idêntico ao de S1.65, incluindo ordenação de chaves, espaçamento, ASCII, sem valores NaN/Infinity e exatamente um `LF` final.
- `_canonical_untrusted_utc` exige texto UTC em formato canônico produzido por `datetime.isoformat()`, comparando `parsed.isoformat() == value`, sem aceitar aliases de data/hora.
- As rejeições ocorrem antes da verificação criptográfica, preservando o gate Ed25519 para o manifesto válido e todas as verificações de custódia, chaves distintas, pins e conteúdo.
- O horário permanece explicitamente **não atestado**. Não há criação de assinatura por essa ferramenta, nem elevação de permissões, captura real ou liberação de produto.

## Testes

Quatro novos métodos exercitam: dois formatos legítimos de hora UTC; sete versões UTC falsas re-assinadas, recusadas antes do verificador SSH; cinco variações de JSON re-assinadas e re-pinnadas recusadas antes da verificação de assinatura; teste de uso obrigatório do novo serializador canônico. As assinaturas dos cenários são produzidas com chaves **descartáveis** pelo `ssh-keygen` real, nunca com chaves de produção. Permanecem as regressões históricas de três signatários distintos, troca de logs, assinaturas alteradas e estado HOLD.

## Limite e pendência externa

[PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) Draft/unmerged; [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) OPEN. Esta etapa valida consistência local de bytes assinados, não atesta identidade do revisor, controle físico/administrativo de host QEMU/libvirt, kernel Arch nativo, PID Ghidra, enforcement conjunto cgroup v2/seccomp, journald ou sequência BEFORE → WORK → AFTER. Não executar Windows PE desconhecido, não fazer merge, APK, OTA nem release.
