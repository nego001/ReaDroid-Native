# ReaDroid Native roadmap

## P0: Core APK inspection
- [x] APK selection using Android Storage Access Framework
- [x] SHA-256, DEX and native library inventory
- [x] PackageManager-based manifest inspection
- [x] Requested permissions and exported component inventory
- [x] Explanatory initial security findings
- [ ] Successful Android APK build in GitHub Actions
- [ ] Binary XML decoding independent of PackageManager
- [ ] Test fixtures and automated scanner unit tests
- [ ] APK signature scheme v2/v3 verification

## P1: File explorer and version comparison
- [ ] Interactive searchable ZIP explorer
- [ ] Side-by-side version differences

## P2: Decompilation
- [ ] DEX metadata browser
- [ ] Compatible embedded decompiler

## P3: Visual APK editor
- [ ] Resource previews and supported edits
- [ ] Modification tracking and backups

## P4: Rebuild and signing
- [ ] Resource rebuild and zip alignment
- [ ] Local signing and signature validation

## P5: Intelligent assistant
- [ ] Offline rule-based findings explanations
- [ ] Optional on-device inference

## Build blocker
GitHub Actions runs currently fail before any step starts; the last checked run has runner_id 0 and an empty steps array. Check repository Actions policies, runner availability, and billing/usage restrictions in GitHub Settings. A successful build has not yet been observed.
