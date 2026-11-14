# PE-S2.16 | Suplemento **v2** assinado para evidência de libvirt; release HOLD

Status: código e testes CI. **Não houve captura nova de VM Arch nativa independente nem homologação externa.** Não executar executáveis Windows desconhecidos, não mesclar a PR #47, não publicar APK/OTA.

## Motivação

A PE-S2.15 criou `reviewer-host-libvirt-domstats.txt` como evidência *complementar*, mas o manifesto S1.63 só assina os quatro registros originais. Inserir o quinto arquivo silenciosamente no S1.63 seria uma mudança incompatível no schema e, pior, poderia sugerir aprovação de segurança inexistente.

A PE-S2.16 define um **documento adicional versionado**, `external-host-domstats-supplement-v2.json`, com assinatura separada `external-host-domstats-supplement-v2.sig` e namespace OpenSSH **`negresco-pe-s2-16-host-domstats-supplement-v2`**. O S1.63 v1 permanece byte a byte intocado. A assinatura v2 cobre os hashes explicitamente pinados do manifesto e assinatura v1, os dois primeiros registros host/guest, a sidecar de estatísticas, o commit, desafio, domínio/UUID, ID de sessão de fora da VM e a chave pública do observador. A sidecar **não é assinada pelo S1.63 v1**; é referenciada pelo manifesto adicional assinado v2. Todos os campos de atestação e release são `false`.

## Ordem de operações real para um revisor independente

1. Em um host QEMU/libvirt que o revisor controla, usar as ferramentas S1.70 e S1.71 para obter registros reais do domínio/guest. Piná-los fora do host do operador.
2. Antes do manifesto assinado v1, coletar a sidecar via PE-S2.15 `--capture-from-independent-host`. Guardar seu SHA-256 *externamente*; os comandos são readonly e limitado a uma VM. **Não usar na máquina pessoal ou guest do operador.**
3. Preparar o inventário externo com S1.65, exigindo os quatro logs já coletados e ID de sessão pinado. Assinar o manifesto S1.63 pelo observador com `ssh-keygen -Y sign`, em seu próprio namespace v1. Validar as três identidades separadas e o conjunto S1.63.
4. Preparar o suplemento com `python -B tools/pe_arch_vm_s2_16_signed_domstats_extension.py --observer-dir ... --custody-dir ...` **mais os 19 parâmetros obrigatórios `--expected-...`**, incluindo `--expected-domstats-sha256`, `--expected-v1-manifest-sha256`, `--expected-v1-signature-sha256`. O programa verifica novamente o S1.63 com assinatura válida, as observações antigas e a sidecar antes de publicar, sem sobrescrever. A chamada padrão apenas prepara o JSON; **não acessa chave privada**.
5. Somente o observador autorizado, em seu domínio de confiança, assina **a extensão v2**, separada da v1. Exemplo no host do revisor:

   ```sh
   ssh-keygen -Y sign -f /private/reviewer/observer_ed25519 \
     -n negresco-pe-s2-16-host-domstats-supplement-v2 \
     /private/observer/external-host-domstats-supplement-v2.json
   # Guardar/renomear o .json.sig criado para external-host-domstats-supplement-v2.sig
   ```

6. Executar o mesmo verificador com `--verify-existing`, **somado aos dois SHA-256 extras escolhidos externamente**: `--expected-extension-manifest-sha256` e `--expected-extension-signature-sha256`. Isso valida assinatura Ed25519 no namespace próprio, formato canônico, hashes e o vínculo v1 + sidecar. **Até validação correta encerra com código 2 e status HOLD; não liberar release a partir desse código.**

## Limitações

O suplemento prova que **uma chave pinada assinou aqueles bytes**, e que o quinto arquivo bate com o SHA-256 incorporado. Não prova que o host foi provisionado de modo independente, que os contadores da VM não foram fabricados, nem isolamento do kernel do guest. O fato de `domstats` relatar `cpu.time` não comprova cgroups v2, seccomp, tamanho de `/work`, quota do journal ou encerramento dos descendentes. Para homologar, um observador independente ainda deve fornecer coleta bruta, autoria e controle do host, vínculos da sessão e prova simultânea dos controles no Arch nativo.

A CI usa dados sintéticos e **assinaturas Ed25519 de chaves temporárias reais**; não consulta nenhum host real. PR #47 permanece Draft; sem merge/OTA/APK.
