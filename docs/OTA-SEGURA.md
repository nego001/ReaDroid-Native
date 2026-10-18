# NegrescoDroid • distribuição OTA segura

## Situação e limites atuais
O caminho de verificação criptográfica existe, mas está **desabilitado para rede** até que o mantenedor
configure o endpoint HTTPS por canal e incorpore a chave pública de confiança em `OtaConfig.java`.
Nenhuma chave privada ou certificado de assinatura deve ser publicado no código-fonte.

Fluxo preparado:
1. Selecionar canal Estável ou Beta; cada canal tem seu próprio feed JSON assinado.
2. Baixar no worker um envelope HTTPS de até 64 KiB, sem redirecionamentos.
3. Verificar assinatura RSA/SHA-256 sobre os **bytes UTF-8 exatos de `payload`**,
   usando uma chave pública fixada no aplicativo.
4. Rejeitar canal errado, `versionCode` não superior ao instalado, URL não HTTPS,
   metadados inválidos e manifesto maior que os limites.
5. Após confirmação, baixar APK no cache privado por HTTPS. Permitir no máximo
   três redirecionamentos, limitados ao mesmo host ou `github.com` → CDN oficial
   `release-assets.githubusercontent.com` / `objects.githubusercontent.com`.
6. Conferir tamanho exato, SHA-256, mesmo package ID, versão superior e certificado
   de assinatura do Android compatível (API 26–27 via assinaturas legadas; API 28+ via\n   SigningInfo). Limpar o arquivo se houver falha.

**Não existe instalação automática nem silenciosa.** No estágio atual o APK validado
é excluído depois do teste. Um instalador com consentimento explícito do Android
depende de nova etapa e de testes reais.

## Duas chaves com funções diferentes

- **Assinatura do APK Android:** manter um único keystore de distribuição em local
  seguro, com backup protegido. O Android exigirá compatibilidade com a assinatura
  instalada para aceitar a atualização. Manter `applicationId = com.readroid.app`.
- **Assinatura do manifesto OTA:** chave **RSA 3072 bits** separada, cuja chave privada
  fica offline; o aplicativo embute apenas a pública SPKI/X.509 em Base64.

A Preview 1 do GitHub Actions foi gerada como **debug** (`versionCode = 1`).
Chaves de debug do runner podem mudar entre builds. **Não prometer atualização OTA por
cima dessa Preview.** Pode ser necessária desinstalação da Preview (com perda dos
dados locais), seguida da instalação inicial de uma versão assinada com a chave
de distribuição estável. Depois disso, todas as atualizações devem preservar essa chave.

## Gerar a chave de manifesto offline

Execute estes comandos em um computador confiável com OpenSSL:

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out ota-private.pem
openssl pkey -in ota-private.pem -pubout -out ota-public.pem
openssl pkey -pubin -in ota-public.pem -outform DER -out ota-public.der
```

No Windows PowerShell, copie para `OtaConfig.TRUSTED_RELEASE_PUBLIC_KEY` o texto
retornado por:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("ota-public.der"))
```

Proteja `ota-private.pem` e nunca o coloque no GitHub, em chats públicos,
em artefatos de Actions ou dentro do APK.

## Criar envelope OTA para um APK de distribuição já assinado

Depois de publicar um APK com versão **superior** e assinatura Android compatível:

```bash
python tools/sign_ota_manifest.py \
  --apk NegrescoDroid-signed.apk \
  --url https://github.com/nego001/ReaDroid-Native/releases/download/TAG/NegrescoDroid-signed.apk \
  --version-code 2 --version-name 0.2.0 --channel beta \
  --private-key ota-private.pem --notes-file notas.txt \
  --output beta.json
```

O utilitário calcula SHA-256 e tamanho reais do APK e gera um envelope
`{"payload":"<JSON serializado>","signature":"<RSA Base64>"}`.
O `versionCode` e `versionName` devem ser **iguais aos metadados internos do APK**.

Publique o `beta.json` ou `stable.json` em URL HTTPS estável.
Configure `BETA_RELEASE_ENDPOINT` ou `STABLE_RELEASE_ENDPOINT`
para a URL do manifesto assinado. Não aponte para a página HTML de Releases
nem para um APK diretamente. Recompile o aplicativo depois de incorporar a
chave pública; distribuir só um novo JSON não substitui a confiança fixada.

O fluxo de teste da assinatura roda no GitHub Actions com uma chave de teste
**efêmera**. Essa chave de teste jamais deve ser usada em produção.

## Portões para habilitar OTA real
- [x] Verificação de manifesto RSA/SHA-256 e SHA-256/tamanho do APK
- [x] Comparação de identidade, versão e assinatura Android (API 26+)
- [x] Suporte limitado ao redirecionamento do GitHub Releases
- [x] Feeds separados por canal e ferramenta de assinatura de manifesto
- [x] Teste automatizado com chave efêmera
- [ ] Keystore de distribuição persistente e rotina de backup seguros
- [ ] Chave pública real fixada no aplicativo e feeds assinados publicados
- [ ] Política de incremento de versionCode e release reproduzível
- [ ] Testes reais de download/certificado em Android 8–15+
- [ ] Instalador com aprovação explícita do usuário, recuperação e diagnóstico

Não alterar os controles de assinatura, não aceitar metadados não assinados
como autorização para download, e jamais instalar de forma silenciosa.
