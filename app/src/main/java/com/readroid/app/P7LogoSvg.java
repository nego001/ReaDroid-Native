package com.readroid.app;

import android.content.Context;
import android.net.Uri;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * Local editable vector logo export, separate from the existing PNG renderer.
 * SVG text uses installed viewer fonts and is not guaranteed to be pixel-identical
 * to Android Canvas. It never edits application identity, APK or edit plans.
 */
public final class P7LogoSvg {
    private P7LogoSvg() {}

    /** XML 1.0 text escaping with rejection of invalid Unicode scalar values. */
    private static String xmlText(String value) {
        StringBuilder escaped = new StringBuilder(value.length() + 12);
        for (int i = 0; i < value.length();) {
            int cp = value.codePointAt(i);
            if (!(cp == 9 || cp == 10 || cp == 13 ||
                    (cp >= 0x20 && cp <= 0xD7FF) ||
                    (cp >= 0xE000 && cp <= 0xFFFD) ||
                    (cp >= 0x10000 && cp <= 0x10FFFF)))
                throw new IllegalArgumentException("Texto incompatível com SVG");
            switch (cp) {
                case '&': escaped.append("&amp;"); break;
                case '<': escaped.append("&lt;"); break;
                case '>': escaped.append("&gt;"); break;
                case '"': escaped.append("&quot;"); break;
                case '\'': escaped.append("&apos;"); break;
                default: escaped.appendCodePoint(cp);
            }
            i += Character.charCount(cp);
        }
        return escaped.toString();
    }

    /** Bounded SVG with shapes and editable vector text, no external resources. */
    public static String build(P7LogoWorkshop.Spec spec) {
        if (spec == null) throw new IllegalArgumentException("Logo vazio");
        String name = xmlText(spec.name);
        String subtitle = xmlText(spec.subtitle);
        int firstEnd = spec.name.offsetByCodePoints(0, 1);
        String initial = xmlText(spec.name.substring(0, firstEnd)
            .toUpperCase(Locale.ROOT));
        String accent = String.format(Locale.ROOT, "#%06X",
            P7LogoWorkshop.accentColor(spec) & 0xFFFFFF);
        StringBuilder xml = new StringBuilder(1500);
        xml.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
        xml.append("<svg xmlns=\"http://www.w3.org/2000/svg\" ")
            .append("width=\"1024\" height=\"512\" viewBox=\"0 0 1024 512\" ")
            .append("role=\"img\" aria-label=\"Logo vetorial personalizado\">\n");
        if (spec.background == 1)
            xml.append("  <rect width=\"1024\" height=\"512\" fill=\"#000000\"/>\n");
        xml.append("  <rect x=\"72\" y=\"142\" width=\"178\" height=\"178\" ")
            .append("rx=\"52\" fill=\"").append(accent).append("\"/>\n");
        xml.append("  <text x=\"161\" y=\"263\" text-anchor=\"middle\" ")
            .append("font-family=\"sans-serif\" font-weight=\"bold\" ")
            .append("font-size=\"106\" fill=\"#FFFFFF\">")
            .append(initial).append("</text>\n");
        xml.append("  <text x=\"295\" y=\"240\" font-family=\"sans-serif\" ")
            .append("font-weight=\"bold\" font-size=\"76\" fill=\"")
            .append(accent).append("\"");
        if (spec.name.codePointCount(0, spec.name.length()) > 17)
            xml.append(" textLength=\"666\" lengthAdjust=\"spacingAndGlyphs\"");
        xml.append(">").append(name).append("</text>\n");
        xml.append("  <text x=\"299\" y=\"305\" font-family=\"sans-serif\" ")
            .append("font-size=\"31\" fill=\"#9AAFC8\"");
        if (spec.subtitle.codePointCount(0, spec.subtitle.length()) > 32)
            xml.append(" textLength=\"670\" lengthAdjust=\"spacingAndGlyphs\"");
        xml.append(">").append(subtitle).append("</text>\n");
        xml.append("  <rect x=\"296\" y=\"352\" width=\"464\" height=\"5\" ")
            .append("rx=\"2\" fill=\"").append(accent).append("\"/>\n");
        xml.append("</svg>\n");
        return xml.toString();
    }

    /** SAF document URI is mandatory; no filesystem path or APK mutation. */
    public static void export(Context context, P7LogoWorkshop.Spec spec, Uri destination)
            throws IOException {
        if (context == null || destination == null
                || !"content".equals(destination.getScheme()))
            throw new IOException("Destino de exportação SVG não autorizado");
        final byte[] utf8 = build(spec).getBytes(StandardCharsets.UTF_8);
        try (OutputStream stream =
                context.getContentResolver().openOutputStream(destination, "w")) {
            if (stream == null) throw new IOException("Não foi possível gravar o SVG");
            stream.write(utf8);
            stream.flush();
        }
    }
}
