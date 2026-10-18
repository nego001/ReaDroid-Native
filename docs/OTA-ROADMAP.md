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
