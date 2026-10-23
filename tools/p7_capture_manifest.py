#!/usr/bin/env python3
"""Inventory actual P7 Android CI screenshot files, without claiming 1:1 fidelity.

Run after the regular, compact and 200%-font emulator smokes. Screenshots
come from 'adb exec-out screencap -p' in earlier steps, never mock assets.
Structural PNG validation and hashes are evidence bookkeeping, not visual
approval: only byte-identical approved references enable later comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

try:
    from tools.p7_compact_smoke import parse_wm, viewport_pixels
    from tools.p7_reference_assets import check_references
except ImportError:
    from p7_compact_smoke import parse_wm, viewport_pixels
    from p7_reference_assets import check_references

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 16 * 1024 * 1024
SCREENS = (
    ("home", "normal", "p7-brand-android-{api}.png"),
    ("explorer", "normal", "p7-explorer-android-{api}.png"),
    ("explorer_populated", "normal", "p7-explorer-populated-android-{api}.png"),
    ("security", "normal", "p7-security-android-{api}.png"),
    ("build", "normal", "p7-build-android-{api}.png"),
    ("design", "normal", "p7-design-android-{api}.png"),
    ("icon_workshop", "normal", "p7-icon-workshop-android-{api}.png"),
    ("logo_workshop", "normal", "p7-logo-workshop-android-{api}.png"),
    ("home", "compact_320dp_font_130pct", "p7-compact-inicio-android-{api}.png"),
    ("explorer", "compact_320dp_font_130pct", "p7-compact-arquivos-android-{api}.png"),
    ("design", "compact_320dp_font_130pct", "p7-compact-design-android-{api}.png"),
    ("home", "normal_font_200pct", "p7-large-text-inicio-android-{api}.png"),
    ("explorer", "normal_font_200pct", "p7-large-text-arquivos-android-{api}.png"),
    ("design", "normal_font_200pct", "p7-large-text-design-android-{api}.png"),
)


class ScreenshotEvidenceError(ValueError):
    """Required genuine CI screenshot is absent or structurally invalid."""


def _validate_png_pixels(compressed, width, height, color, filename):
    """Validate bounded zlib scanlines, not visual similarity or provenance."""
    scanline_bytes = 1 + width * (3 if color == 2 else 4)
    required = scanline_bytes * height
    observed = 0
    offset = 0

    def consume(block):
        nonlocal observed, offset
        if observed + len(block) > required:
            raise ScreenshotEvidenceError(
                f"PNG pixels exceed declared size: {filename}")
        index = 0
        while index < len(block):
            if offset == 0 and block[index] > 4:
                raise ScreenshotEvidenceError(
                    f"Invalid PNG row filter: {filename}")
            length = min(scanline_bytes - offset, len(block) - index)
            offset = (offset + length) % scanline_bytes
            index += length
        observed += len(block)

    decompressor = zlib.decompressobj()
    try:
        for position in range(0, len(compressed), 65536):
            pending = compressed[position:position + 65536]
            while pending:
                block = decompressor.decompress(pending, 65536)
                consume(block)
                if decompressor.unused_data:
                    raise ScreenshotEvidenceError(
                        f"Trailing PNG compressed data: {filename}")
                pending = decompressor.unconsumed_tail
        while True:
            block = decompressor.decompress(b"", 65536)
            if not block:
                break
            consume(block)
    except zlib.error as error:
        raise ScreenshotEvidenceError(
            f"Corrupted PNG pixels: {filename}") from error
    if not decompressor.eof or observed != required or offset != 0:
        raise ScreenshotEvidenceError(
            f"Truncated PNG pixel data: {filename}")


def inspect_png(path):
    """Verify PNG chunk framing/CRCs and return width, height and SHA-256.

    This does not inspect decoded pixels or establish provenance by itself.
    """
    if not path.is_file():
        raise ScreenshotEvidenceError(f"Required screenshot missing: {path.name}")
    size = path.stat().st_size
    if not 45 <= size <= MAX_BYTES:
        raise ScreenshotEvidenceError(f"Invalid screenshot file size: {path.name}")
    data = path.read_bytes()
    if not data.startswith(PNG_MAGIC):
        raise ScreenshotEvidenceError(f"Invalid PNG signature: {path.name}")
    position = len(PNG_MAGIC)
    dimensions = None
    seen_image_data = False
    seen_end = False
    idat_parts = []
    idat_closed = False
    while position < len(data):
        if len(data) - position < 12:
            raise ScreenshotEvidenceError(f"Truncated PNG chunk: {path.name}")
        length = struct.unpack_from(">I", data, position)[0]
        end = position + 12 + length
        if end > len(data):
            raise ScreenshotEvidenceError(f"Invalid PNG chunk length: {path.name}")
        tag = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + length]
        expected_crc = struct.unpack_from(">I", data, position + 8 + length)[0]
        if zlib.crc32(tag + payload) & 0xffffffff != expected_crc:
            raise ScreenshotEvidenceError(f"PNG CRC mismatch: {path.name}")
        if dimensions is None:
            if tag != b"IHDR" or length != 13:
                raise ScreenshotEvidenceError(f"Invalid PNG IHDR: {path.name}")
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", payload))
            if (not 0 < width <= 8192 or not 0 < height <= 8192
                    or depth != 8 or color not in (2, 6)
                    or compression != 0 or filtering != 0
                    or interlace != 0):
                raise ScreenshotEvidenceError(f"Unsupported PNG format: {path.name}")
            dimensions = (width, height)
        elif tag == b"IHDR":
            raise ScreenshotEvidenceError(f"Duplicate PNG IHDR: {path.name}")
        if tag == b"IDAT":
            if idat_closed:
                raise ScreenshotEvidenceError(
                    f"Non-contiguous PNG IDAT: {path.name}")
            if length == 0:
                raise ScreenshotEvidenceError(f"Empty PNG IDAT: {path.name}")
            seen_image_data = True
            idat_parts.append(payload)
        elif seen_image_data:
            idat_closed = True
        position = end
        if tag == b"IEND":
            if length != 0 or position != len(data):
                raise ScreenshotEvidenceError(f"Invalid PNG ending: {path.name}")
            seen_end = True
            break
    if not seen_image_data or not seen_end:
        raise ScreenshotEvidenceError(f"PNG missing data or IEND: {path.name}")
    _validate_png_pixels(b"".join(idat_parts), width, height, color, path.name)
    return dimensions, hashlib.sha256(data).hexdigest(), size


def build_manifest(directory, api, viewport, density, reference_dir=None):
    """Validate all fourteen screenshots; never silently omit a failed scene."""
    if str(api) not in ("29", "35"):
        raise ScreenshotEvidenceError("Unexpected Android API for P7 evidence")
    width, height = viewport
    if density <= 0 or width <= 0 or height <= 0:
        raise ScreenshotEvidenceError("Invalid emulator geometry")
    compact_size = viewport_pixels(320, 720, density)
    samples = []
    seen_digests = {}
    for section, scenario, template in SCREENS:
        filename = template.format(api=api)
        (actual_width, actual_height), digest, size = inspect_png(
            Path(directory) / filename)
        expected_width, expected_height = (compact_size
            if scenario == "compact_320dp_font_130pct" else viewport)
        if (actual_width, actual_height) != (expected_width, expected_height):
            raise ScreenshotEvidenceError(
                f"{filename}: {actual_width}x{actual_height} PNG "
                f"does not match {expected_width}x{expected_height} emulator")
        # A valid PNG can be copied and renamed to impersonate another
        # scene. Every one of the 14 required screenshots must be unique
        # bytes, even when two pages use the same baseline dimensions.
        if digest in seen_digests:
            raise ScreenshotEvidenceError(
                f"Duplicate screenshot evidence: {filename} "
                f"is identical to {seen_digests[digest]}")
        seen_digests[digest] = filename
        samples.append({
            "screen": section,
            "scenario": scenario,
            "filename": filename,
            "size_bytes": size,
            "width_px": actual_width,
            "height_px": actual_height,
            "sha256": digest,
        })
    if reference_dir is None:
        refs_verified, _ = check_references()
    else:
        refs_verified, _ = check_references(reference_dir)
    return {
        "schema_version": 1,
        "source": "GitHub Actions / Android emulator / adb exec-out screencap",
        "validation_scope": "PNG structure, deflate scanlines, dimensions, hashes and unique screenshot evidence; not visual similarity",
        "pixel_perfect_approved": False,
        "physical_device_approved": False,
        "official_references": "VERIFIED" if refs_verified else "BLOCKED",
        "emulator": {
            "android_api": int(api),
            "baseline_width_px": width,
            "baseline_height_px": height,
            "density_dpi": density,
            "compact_width_px": compact_size[0],
            "compact_height_px": compact_size[1],
        },
        "screenshots": samples,
    }


def adb_output(*args):
    return subprocess.check_output(["adb", *args], text=True, timeout=30).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    api = adb_output("shell", "getprop", "ro.build.version.sdk")
    viewport, _ = parse_wm(adb_output("shell", "wm", "size"), "size")
    (density,), _ = parse_wm(adb_output("shell", "wm", "density"), "density")
    try:
        report = build_manifest(args.directory, api, viewport, density)
    except (ScreenshotEvidenceError, OSError) as error:
        print(f"P7_EVIDENCE_FAIL api={api}: {error}")
        return 1
    output = args.output or Path(f"p7-evidence-android-{api}.json")
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    temp.replace(output)
    print(f"P7_EVIDENCE_PASS api={api} screenshots={len(report['screenshots'])} "
          f"references={report['official_references']} file={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
