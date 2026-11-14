# PE-S2.46 | S1.70 rejeita capturas libvirt inconsistentes antes de gravar (HOLD)

## Lacuna real entre produtor e leitores

O capturador S1.70 aceitava um `dominfo` com `Name`, `UUID` e `State` coerentes, mas contendo uma linha adicional como `release_authorized=true` ou `source_commit=`. Nessa situação, o S1.70 **publicava e calculava o hash** da captura, enquanto S1.71 e S1.73 recusavam o mesmo arquivo mais tarde por conter marcadores do envelope inseridos no bloco `dominfo`. Outro descompasso: S1.70 admitia `\r`/`\t` e DEL no stdout, embora as leituras do pacote posterior exigissem registros separados por LF sem controles.

Isso significa evidência **local autocontraditória**, não prova de que um host real tenha sido manipulado ou atestado.

## Alteração

- `tools/pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`: introduz `DOMINFO_RESERVED_PREFIXES` para negar no bloco `dominfo` os marcadores reservados de identificação, challenge, estado, URI, atestação e autorização. Linhas vazias internas também são rejeitadas antes de `_publish_new_file`.
- `_checked_text` rejeita CR, TAB, DEL e outros caracteres de controle, exceto LF. O formato da captura continua preservando o stdout aceito, sem limpar seletivamente evidência potencialmente enganosa.
- `tools/pe_arch_vm_s1_71_guestinfo_os_capture.py` reutiliza a lista idêntica de marcadores do S1.70. S1.73 já exige a verificação de snapshot S1.71, evitando políticas independentes que possam divergir.
- Não modifica as assinaturas Ed25519 V1/V2/V3, hashes externos, esquema final ou chamadas `virsh --readonly`. Sem acesso live novo ou envio de dados privados.

## Testes adicionados

Quatro métodos em `tests/test_pe_arch_vm_s1_70_readonly_libvirt_host_capture.py`:
1. Captura sintética válida continua aceita pelo próprio parser S1.71 e compartilha os marcadores.
2. `dominfo` forjado com identidade/URI ou falsos campos de release/atestação é recusado **sem publicação**.
3. Linha em branco interna no `dominfo` é recusada sem arquivo.
4. CR, TAB e DEL no stdout são recusados antes de publicar o registro.

Os testes usam `virsh` simulado por `unittest.mock`, **não executam QEMU/libvirt nem homologam uma VM Arch**. A suíte preexistente inclui testes de falha de rede/execução, controle de tamanho, arquivo privado e modo read-only. O workflow PE Sandbox executa ambas as suítes em Ubuntu e Arch userspace.

## Limites de segurança

Um arquivo S1.70 compatível com S1.71/S1.73 e com SHA-256 correto prova apenas consistência estrutural local. Não autentica host independente, kernel convidado, cgroups v2, seccomp, journald, eliminação dos descendentes ou encadeamento BEFORE → WORK → AFTER.

A [Issue #48](https://github.com/nego001/ReaDroid-Native/issues/48) continua **OPEN**. A [PR #47](https://github.com/nego001/ReaDroid-Native/pull/47) permanece **Draft**, sem merge, APK, OTA, release ou execução de PE desconhecido. `independent_vm_attestation=false` e `release_authorized=false` continuam inalterados.
