# PE-S2.13 | Dois registros externos deixam de aceitar texto genérico

## Defeito corrigido

A assinatura S1.63 verificava hashes de quatro registros, mas o gate semântico S1.73/S1.65/S1.64 só exigia conteúdo estruturado para host e guest. Os logs finais de `cgroup/seccomp` e `scope_cleanup` podiam ser frases assinadas sem referência de sessão, processo ou escopo. **Assinar texto sem conteúdo verificável não prova a segurança do sistema.**

## Mudança

O novo `pe_arch_vm_s2_13_runtime_log_chain.py` exige duas observações no formato exato ASCII: SHA dos dois primeiros registros externamente pinados, `source_commit`, desafio, domínio/UUID, `session_id` e `scope` idênticos, e o digest SHA-256 do texto de runtime no texto de cleanup. Rejeita valores auto-relatados impossíveis (quota ilimitada, seccomp desativado, cgroup ainda populado, escopo ativo ou alegações de release). O preparador S1.65 precisa passar por essa checagem antes de criar o manifesto; a revisão S1.64 volta a verificá-la **depois de validar as três assinaturas**, assegurando que os mesmos dois textos ainda coincidam com hashes do manifesto.

As regressões cobrem campos duplicados, logs antigos genéricos, misturas de sessão, digest incompatível, valores mentirosos e logs re-hashados e novamente assinados. Testes usam identidades e chaves Ed25519 descartáveis e textos explicitamente sintéticos.

## Limites não resolvidos

`session_id`, PID, cgroup e seccomp continuam **declarações em texto**, não evidência de sensores autenticados, nem prova de execução no mesmo kernel ou VM. Revisor externo ainda precisa apresentar o material bruto correlacionado ao SHA e desafio, controle independente do hipervisor, journald e cleanup real. Este gate não contata host, VM ou serviço, não executa executáveis Windows e não autoriza merge, APK ou OTA. PR #47 deve permanecer em Draft.
