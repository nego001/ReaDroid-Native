# NegrescoDroid | Atualizações OTA

Status: planejado, ainda não implementado.

## Objetivo
Permitir atualização do próprio NegrescoDroid pelo Android, sem exigir download manual no GitHub.

## Escopo
- Verificação manual e periódica de novas versões (sem verificações excessivas).
- Canais estável e beta, com escolha explícita do usuário.
- Manifesto de releases HTTPS com versão, versionCode, URL, SHA-256, tamanho, notas e assinatura digital do manifesto.
- Confiança ancorada em chave pública incorporada ao app; rotação de chaves planejada e verificável.
- Download em cache privado, progresso, retomada quando suportada, limites de tamanho, cancelamento e limpeza.
- Verificação de assinatura do manifesto, hash do APK e identidade de assinatura Android antes de oferecer instalação.
- Impedir downgrade não autorizado, impedir troca de canal silenciosa e não executar código baixado.
- Instalação via fluxo oficial PackageInstaller com confirmação do usuário; respeitar políticas Android e distribuição por loja.
- Tratamento de falha de rede, ausência de espaço, rollback manual documentado e acessibilidade.
- Testes unitários, instrumentados e testes reais em aparelhos Android suportados.

## Etapas
1. Definir modelo de publicação, versionamento e formato do manifesto.
2. Implementar verificação segura de atualização, sem instalação.
3. Implementar download com validação criptográfica.
4. Implementar fluxo de instalação autorizado pelo usuário.
5. Testar releases assinados, versões beta/estáveis, falhas e migrações.

## Restrições
OTA atualiza o aplicativo NegrescoDroid, não os APKs de terceiros analisados.
Não prometer instalação silenciosa, assinatura automática de APKs modificados ou atualização funcional antes de testes reais.

## Formato inicial do envelope assinado

```json
{
  "payload": "{\"versionCode\":2,\"versionName\":\"0.2.0\",\"channel\":\"stable\",\"downloadUrl\":\"https://updates.example.org/app.apk\",\"sha256\":\"<64 hex chars>\",\"sizeBytes\":123456,\"notes\":\"Mudanças\"}",
  "signature": "<base64 RSA-SHA256 sobre os bytes UTF-8 exatos de payload>"
}
```

O endereço acima é apenas ilustrativo e não é um endpoint configurado.
A chave pública RSA X.509/SPKI confiável deve ser incorporada à aplicação antes de qualquer consulta.
Sem chave configurada, a verificação falha de modo seguro. Nunca aceitar metadados sem assinatura válida.
A verificação do manifesto não substitui a conferência da assinatura Android do APK instalado.

## Implementação parcial (2026-10-18)

- `OtaManifestVerifier`: valida envelope assinado RSA-SHA256.
- `OtaUpdateChecker`: busca HTTPS sem redirects e aceita somente manifesto autenticado.
- `OtaApkDownloader`: download em arquivo temporário privado, limite de tamanho e SHA-256, sem instalação.
- **Ainda falta:** configurar chave pública confiável e endpoint real; ligar a consulta e o download à UI; conferir identidade de assinatura do APK; integrar instalador do Android; testar no dispositivo.
- Não disponibilizar o arquivo baixado para instalação antes de conferir também a assinatura Android e o packageName.

## Verificação de identidade de pacote

`OtaPackageVerifier` compara o `packageName`, o `versionCode` e os certificados de assinatura apresentados pelo PackageManager com os do aplicativo instalado. Por enquanto exige os mesmos certificados, sem suporte a rotação de chaves. É um componente isolado, não conectado à instalação. Testar em dispositivos reais antes de liberar OTA; o instalador Android permanece responsável pela validação final do pacote.
