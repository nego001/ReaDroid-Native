#!/usr/bin/env python3
"""Build an offline cross-API visual review from verified P7 emulator artifacts.

Never call reference availability or valid PNGs a pixel-perfect approval.
The official mockup contains promotional smartphone composites, not raw UI frames.
"""
import argparse
import base64
import html
import json
from pathlib import Path

try:
    from tools import p7_capture_manifest as capture
    from tools import p7_reference_assets as references
    from tools import p7_visual_review_board as board
except ImportError:
    import p7_capture_manifest as capture
    import p7_reference_assets as references
    import p7_visual_review_board as board

SCENES = (("home", "Início"), ("explorer", "Explorador"),
          ("design", "Design Studio"))
STYLE = """
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#07111b;
color:#eef6ff}body{max-width:1450px;margin:auto;padding:24px}
h1{font-size:clamp(24px,3vw,44px)}h2{margin-top:34px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
figure{margin:0;background:#102031;border:1px solid #32516b;
padding:12px;border-radius:14px}img{max-width:100%;max-height:700px;
display:block;margin:auto}figcaption{margin-top:10px;font-size:14px}
.notice{border:1px solid #48586a;padding:14px;border-radius:12px}
.small{color:#adc1d8;font-size:13px;line-height:1.6}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
"""


class CrossApiReviewError(ValueError):
    pass


def _image(path):
    """Embed only bytes that verified_manifest or check_references validated."""
    return "data:image/png;base64," + base64.b64encode(
        Path(path).read_bytes()).decode("ascii")


def render_review(api29_dir, api35_dir, reference_dir):
    roots = {29: Path(api29_dir), 35: Path(api35_dir)}
    reference_dir = Path(reference_dir)
    manifests = {}
    for api, root in roots.items():
        manifest = root / f"p7-evidence-android-{api}.json"
        evidence = board.verified_manifest(manifest, root, reference_dir)
        if evidence["emulator"]["android_api"] != api:
            raise CrossApiReviewError("Evidence is assigned to the wrong API")
        manifests[api] = evidence
    references_ok = all(m["official_references"] == "VERIFIED"
                        for m in manifests.values())
    parts = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<meta http-equiv='Content-Security-Policy' "
        "content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'\">",
        "<title>NegrecoDroid P7 · Android 10 x 15</title>",
        f"<style>{STYLE}</style></head><body>",
        "<h1>NegrecoDroid · Auditoria visual P7</h1>",
        "<p>Comparativo de capturas reais verificadas do Android 10/API 29 "
        "e Android 15/API 35, com as referências originais quando disponíveis. "
        "As artes são painéis promocionais com telefones em perspectiva, "
        "não screenshots Android para comparação pixel a pixel.</p>",
        "<div class='notice'><strong>Referências oficiais: "
        + ("VERIFICADAS" if references_ok else "BLOQUEADAS") + "</strong>. "
        "<strong>Fidelidade visual 1:1: NÃO APROVADA.</strong> "
        "<strong>Galaxy A55 físico: NÃO HOMOLOGADO.</strong> "
        "Há 13 screenshots verificadas em cada API. "
        "Integridade de PNG não prova semelhança visual.</div>",
        "<h2>Imagens oficiais da referência</h2><div class='grid'>",
    ]
    for filename in references.REFERENCES:
        safe = html.escape(filename)
        parts.append("<figure>")
        if references_ok:
            parts.append(f"<img src='{_image(reference_dir / filename)}' "
                         f"alt='Referência oficial {safe}'>")
        else:
            parts.append("<p>PNG original ausente ou divergente. "
                         "Nenhuma imagem substituta foi usada.</p>")
        parts.append(f"<figcaption>{safe}</figcaption></figure>")
    parts.append("</div>")
    normal_screens = {section: template for section, scenario, template
                      in capture.SCREENS if scenario == "normal"}
    for scene, title in SCENES:
        parts.append(f"<h2>{html.escape(title)}</h2><div class='grid'>")
        parts.append("<figure><p>Arte oficial completa disponível na seção "
                     "de referências acima. Não há crop de viewport validado "
                     "para este painel promocional.</p><figcaption>"
                     "Composição aprovada, escala não alinhada</figcaption></figure>")
        for api in (29, 35):
            filename = normal_screens[scene].format(api=api)
            expected = [sample for sample in manifests[api]["screenshots"]
                        if sample["filename"] == filename]
            if len(expected) != 1:
                raise CrossApiReviewError("Missing baseline screenshot")
            parts.append("<figure>"
                         f"<img src='{_image(roots[api] / filename)}' "
                         f"alt='{html.escape(title)} Android API {api}'>"
                         f"<figcaption>Android API {api}: "
                         f"{expected[0]['width_px']}×{expected[0]['height_px']}"
                         f"<p class='small'>SHA-256: {expected[0]['sha256']}"
                         "</p></figcaption></figure>")
        parts.append("</div>")
    parts.extend([
        "<h2>Pontos de controle manual</h2>",
        "<div class='notice'><p>Compare a hierarquia visual, margens, tipografia, "
        "arte do mascote, cor, estados reais, navegação e alvos de toque. "
        "O Explorador pode aparecer vazio quando não há APK carregado. "
        "Não criar dados fictícios para imitar a prancha.</p>"
        "<p>Valide também os cenários 320 dp/130% e fonte 200% nos manifestos "
        "de cada API; execute a homologação física e TalkBack separadamente. "
        "A aprovação final requer avaliação humana e ensaio no Galaxy A55.</p></div>",
        "</body></html>",
    ])
    return "".join(parts), {
        "api": [29, 35],
        "verified_screenshots": sum(len(m["screenshots"])
                                    for m in manifests.values()),
        "references": "VERIFIED" if references_ok else "BLOCKED",
        "pixel_perfect_approved": False,
        "physical_device_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api29-dir", type=Path, required=True)
    parser.add_argument("--api35-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path,
                        default=references.REFERENCE_DIR)
    parser.add_argument("--output", type=Path,
                        default=Path("p7-cross-api-review.html"))
    args = parser.parse_args()
    try:
        content, summary = render_review(
            args.api29_dir, args.api35_dir, args.reference_dir)
        temporary = args.output.with_suffix(".html.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(args.output)
    except (CrossApiReviewError, board.ReviewBoardError,
            ValueError, KeyError, OSError) as error:
        print(f"P7_CROSS_API_FAIL: {error}", flush=True)
        return 1
    print("P7_CROSS_API_PASS "
          f"screenshots={summary['verified_screenshots']} "
          f"references={summary['references']} "
          "visual_1to1=NOT_APPROVED physical=NOT_APPROVED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
