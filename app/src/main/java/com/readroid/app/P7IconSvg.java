package com.readroid.app;

import android.content.Context;
import android.net.Uri;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * Native vector export for the icon workshop's validated finite palette.
 * Standalone SVG: no scripts, external resources, fonts or user-controlled XML.
 * The paths are editable in vector applications, without modifying APKs.
 */
public final class P7IconSvg {
    private static final String[] COLORS = {
        "#096DFF", "#0AAF83", "#8A4FFF", "#ED6C38", "#161D29"
    };

    private P7IconSvg() {}

    private static void appendSymbol(StringBuilder svg, int symbol) {
        if (symbol == 3) {
            svg.append("  <path fill=\"#FFFFFF\" d=\"");
            for (int i = 0; i < 10; i++) {
                double angle = -Math.PI / 2 + i * Math.PI / 5;
                double r = i % 2 == 0 ? 118 : 49;
                double x = 256 + Math.cos(angle) * r;
                double y = 256 + Math.sin(angle) * r;
                svg.append(i == 0 ? "M " : " L ")
                    .append(String.format(Locale.ROOT, "%.3f %.3f", x, y));
            }
            svg.append(" Z\"/>\n");
            return;
        }

        svg.append("  <path fill=\"none\" stroke=\"#FFFFFF\" ")
            .append("stroke-width=\"25\" stroke-linecap=\"round\" ")
            .append("stroke-linejoin=\"round\" d=\"");
        switch (symbol) {
            case 0:
                svg.append("M 256 126 L 369 166 L 351 298 ")
                    .append("Q 327 358 256 393 Q 185 358 161 298 ")
                    .append("L 143 166 Z ")
                    .append("M 207 255 L 246 294 L 314 221");
                break;
            case 1:
                svg.append("M 223 199 L 175 256 L 223 313 ")
                    .append("M 289 199 L 337 256 L 289 313 ")
                    .append("M 271 180 L 238 332");
                break;
            case 2:
                svg.append("M 147 207 L 203 207 L 228 182 ")
                    .append("L 365 182 L 365 326 L 147 326 Z");
                break;
            default:
                throw new IllegalArgumentException("Símbolo inválido");
        }
        svg.append("\"/>\n");
    }

    public static String build(P7IconWorkshop.Spec spec) {
        if (spec == null) throw new IllegalArgumentException("Ícone vazio");
        // Spec is an immutable, constructor-validated finite set of indices.
        StringBuilder svg = new StringBuilder(1200);
        svg.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
            .append("<svg xmlns=\"http://www.w3.org/2000/svg\" ")
            .append("width=\"512\" height=\"512\" viewBox=\"0 0 512 512\" ")
            .append("role=\"img\" aria-label=\"Ícone vetorial personalizado\">\n");
        if (spec.shape == 1) {
            svg.append("  <circle cx=\"256\" cy=\"256\" r=\"220\" fill=\"")
                .append(COLORS[spec.color]).append("\"/>\n");
        } else {
            svg.append("  <rect x=\"36\" y=\"36\" width=\"440\" height=\"440\" ")
                .append("rx=\"").append(spec.shape == 2 ? 32 : 112)
                .append("\" fill=\"").append(COLORS[spec.color])
                .append("\"/>\n");
        }
        svg.append("  <circle cx=\"256\" cy=\"256\" r=\"153\" ")
            .append("fill=\"none\" stroke=\"#FFFFFF\" ")
            .append("stroke-opacity=\"0.188\" stroke-width=\"6\"/>\n");
        appendSymbol(svg, spec.symbol);
        svg.append("</svg>\n");
        return svg.toString();
    }

    /** Write only to an explicitly selected Android document URI. */
    public static void export(Context context, P7IconWorkshop.Spec spec,
            Uri destination) throws IOException {
        if (context == null || destination == null
                || !"content".equals(destination.getScheme()))
            throw new IOException("Destino de exportação SVG não autorizado");
        byte[] bytes = build(spec).getBytes(StandardCharsets.UTF_8);
        try (OutputStream stream =
                context.getContentResolver().openOutputStream(destination, "w")) {
            if (stream == null) throw new IOException("Não foi possível gravar o SVG");
            stream.write(bytes);
            stream.flush();
        }
    }
}
