#!/usr/bin/env python3
"""Offline P7 visual-review board from verified Android emulator evidence.

The result is a human review aid, NOT automated visual or physical acceptance.
Open it alongside the 14 PNG files from the same downloaded workflow artifact.
Reference artwork is embedded ONLY after the exact original PNGs pass SHA-256.
"""
import argparse
import base64
import html
import json
from pathlib import Path

try:
    from tools import p7_capture_manifest as capture
    from tools import p7_reference_assets as references
except ImportError:
    import p7_capture_manifest as capture
    import p7_reference_assets as references

MAX_MANIFEST_BYTES = 128 * 1024

SCENE_NAMES = {
    "home": "Início",
    "explorer": "Explorador de arquivos",
    "explorer_populated": "Explorador com ZIP sintético de QA",
    "security": "Segurança",
    "build": "Construir",
    "design": "Design Studio",
    "icon_workshop": "Criador de ícones",
    "logo_workshop": "Criador de logotipos",
}
SCENARIO_NAMES = {
    "normal": "Capturas originais do emulador",
    "compact_320dp_font_130pct": "Tela compacta de 320 dp, fonte de 130%",
    "normal_font_200pct": "Fonte ampliada para 200%",
}
STYLE = """
:root { color-scheme:dark; font-family:system-ui,-apple-system,sans-serif;
  background:#070d17;color:#eef5ff; }
* { box-sizing:border-box; }
body { margin:0 auto; padding:clamp(14px,3vw,40px); max-width:1500px; }
h1 { font-size:clamp(1.4rem,3vw,2.3rem);margin:0 0 6px; }
h2 { margin:28px 0 14px;font-size:1.25rem; }
p,li { line-height:1.55; }
.muted { color:#a4b4cb; } .mono { font-family:ui-monospace,monospace;
  word-break:break-all;font-size:.78rem; }
.banner { border:1px solid #314c6b;padding:16px 20px;border-radius:14px;
  background:#102136; }
.blocked { color:#ffd99b;font-weight:700; }
.verify { color:#9bf0c6;font-weight:700; }
.grid { display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));
  gap:16px; }
.figure { margin:0;border:1px solid #263b56;border-radius:14px;
  background:#111e30;overflow:hidden;padding:12px; }
.figure img { display:block;max-width:100%;max-height:690px;object-fit:contain;
  margin:0 auto;border:1px solid #263b56;border-radius:8px; }
.figure h3 { font-size:1rem;margin:10px 2px 6px; }
.art img { max-height:520px; }
.meta { font-size:.8rem;color:#a4b4cb; }
.notice { background:#121e2f;border-left:3px solid #73baff;padding:10px 16px; }
a { color:#86bfff; }
ul { padding-left:22px; }
@media print { body {background:#fff;color:#111;}
  .figure,.banner,.notice {background:#fff;color:#111;}
  .muted,.meta {color:#333;} }
"""


class ReviewBoardError(ValueError):
    """A screenshot, manifest or approval flag does not match real evidence."""


def verified_manifest(manifest_path, screenshots, reference_dir):
    path = Path(manifest_path)
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ReviewBoardError("Manifest absent or unexpectedly large")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        emulator = data["emulator"]
        api = emulator["android_api"]
        viewport = (emulator["baseline_width_px"],
                    emulator["baseline_height_px"])
        density = emulator["density_dpi"]
        expected = capture.build_manifest(
            screenshots, api, viewport, density, reference_dir=reference_dir)
    except (KeyError, ValueError, TypeError, OSError,
            capture.ScreenshotEvidenceError) as error:
        raise ReviewBoardError(f"Invalid P7 screenshot evidence: {error}") from error
    # Require all 14 canonical filenames, real bytes, recomputed hashes,
    # declared viewport/density and honest approval flags.
    if data != expected:
        raise ReviewBoardError(
            "Screenshot manifest mismatches current files or contains "
            "unverified approval, provenance, or reference claims")
    return expected


def render_board(manifest_path, screenshots, reference_dir):
    screenshots = Path(screenshots)
    reference_dir = Path(reference_dir)
    manifest = verified_manifest(manifest_path, screenshots, reference_dir)
    api = manifest["emulator"]["android_api"]
    refs_ok = manifest["official_references"] == "VERIFIED"
    status = ("REFERÊNCIAS VERIFICADAS. REVISÃO HUMANA NECESSÁRIA."
              if refs_ok else "BLOQUEADO: ARTES OFICIAIS AUSENTES OU INVÁLIDAS")
    status_class = "verify" if refs_ok else "blocked"
    parts = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'\">",
        f"<title>P7 · Revisão visual Android {api}</title><style>{STYLE}</style></head><body>",
        f"<h1>NegrecoDroid · Revisão visual P7 · Android API {api}</h1>",
        "<p class='muted'>Capturas reais do workflow. Painel para comparação manual, "
        "não laudo de aprovação pixel a pixel.</p>",
        f"<div class='banner'><p class='{status_class}'>{status}</p>",
        "<p><strong>Visual 1:1:</strong> NÃO APROVADO. "
        "<strong>Teste físico:</strong> NÃO APROVADO. "
        "Verificações funcionais e de PNG não substituem avaliação humana.</p>",
        f"<p class='meta'>Viewport: {manifest['emulator']['baseline_width_px']} × "
        f"{manifest['emulator']['baseline_height_px']} px · "
        f"Densidade: {manifest['emulator']['density_dpi']} dpi · "
        "14 capturas verificadas por SHA-256, dimensão e estrutura PNG.</p></div>",
        "<h2>Artes oficiais vinculantes</h2><div class='grid'>",
    ]
    for name, expected_hash in references.REFERENCES.items():
        safe_name = html.escape(name)
        parts.append("<figure class='figure art'>")
        if refs_ok:
            # Only the exact SHA-256-matched approved bytes may appear here.
            encoded = base64.b64encode(
                (reference_dir / name).read_bytes()).decode("ascii")
            parts.append(f"<img src='data:image/png;base64,{encoded}' "
                         f"alt='Arte original oficial {safe_name}'>")
        else:
            parts.append("<div class='notice'>Imagem oficial não disponível. "
                         "Nenhuma captura ou arte gerada será usada como substituta.</div>")
        parts.append(f"<figcaption><h3>{safe_name}</h3>"
                     f"<p class='mono'>SHA-256 exigido: {expected_hash}</p>"
                     "</figcaption></figure>")
    parts.append("</div>")
    for scenario, title in SCENARIO_NAMES.items():
        parts.append(f"<h2>{html.escape(title)}</h2><div class='grid'>")
        for sample in manifest["screenshots"]:
            if sample["scenario"] != scenario:
                continue
            filename = sample["filename"]  # Canonical verified manifest only.
            label = SCENE_NAMES[sample["screen"]]
            parts.append(
                "<figure class='figure'>"
                f"<img loading='lazy' src='{html.escape(filename, quote=True)}' "
                f"alt='{html.escape(label)} em {html.escape(title)}'>"
                f"<figcaption><h3>{html.escape(label)}</h3>"
                f"<p class='meta'>{sample['width_px']} × {sample['height_px']} px "
                f"· {sample['size_bytes']} bytes</p>"
                f"<p class='mono'>SHA-256: {sample['sha256']}</p>"
                "</figcaption></figure>"
            )
        parts.append("</div>")
    parts.extend([
        "<h2>Critérios para revisão humana 1:1</h2>",
        "<div class='notice'><p><strong>Checklist de inspeção, não aprovação automática.</strong></p>",
        "<ul><li>Comparar a composição de cada seção com as duas artes oficiais, "
        "respeitando que as referências são painéis e não screenshots do aparelho.</li>",
        "<li>Inspecionar mascote, logo, ícones, cores, tipografia, margens, alinhamento, "
        "espessuras, contraste e tamanho dos alvos.</li>",
        "<li>Conferir conteúdo real, rolagem e navegação nas capturas normais, "
        "320 dp/130% e fonte 200%, sem inventar dados ou elementos.</li>",
        "<li>Documentar divergências com região, severidade, imagem, commit e evidência "
        "antes de autorizar a homologação 1:1.</li>",
        "<li>Executar teste físico no Galaxy A55 e registrar aprovação separadamente.</li>",
        "</ul></div>",
        "<p class='muted'>Abra este HTML após extrair o ZIP do GitHub Actions "
        "na mesma pasta dos PNGs. Não há scripts nem acesso à rede.</p>",
        "</body></html>",
    ])
    return "".join(parts), manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("."))
    parser.add_argument("--reference-dir", type=Path,
                        default=references.REFERENCE_DIR)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    api = None
    try:
        # Manifest creation precedes board rendering in the Android workflow.
        candidates = sorted(args.directory.glob("p7-evidence-android-*.json"))
        if args.manifest is None:
            if len(candidates) != 1:
                raise ReviewBoardError("Specify --manifest for one Android API")
            manifest = candidates[0]
        else:
            manifest = args.manifest
        api = json.loads(manifest.read_text(encoding="utf-8"))["emulator"]["android_api"]
        output = args.output or args.directory / f"p7-visual-review-android-{api}.html"
        if output.resolve().parent != args.directory.resolve():
            raise ReviewBoardError("HTML and screenshots must share one directory")
        board, evidence = render_board(manifest, args.directory,
                                       args.reference_dir)
        temporary = output.with_suffix(".html.tmp")
        temporary.write_text(board, encoding="utf-8")
        temporary.replace(output)
    except (ReviewBoardError, ValueError, KeyError, OSError) as error:
        print(f"P7_VISUAL_BOARD_FAIL api={api}: {error}", flush=True)
        return 1
    print(f"P7_VISUAL_BOARD_PASS api={api} "
          f"references={evidence['official_references']} "
          f"visual_1to1=NOT_APPROVED physical=NOT_APPROVED "
          f"file={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
