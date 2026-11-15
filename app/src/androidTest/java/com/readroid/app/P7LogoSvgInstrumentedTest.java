package com.readroid.app;

import android.content.Context;
import android.net.Uri;
import android.util.Xml;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.xmlpull.v1.XmlPullParser;
import static org.junit.Assert.*;

/** Verifies offline, bounded and editable SVG export, without creating an APK. */
@RunWith(AndroidJUnit4.class)
public final class P7LogoSvgInstrumentedTest {
    @Test public void svgEscapesUserTextAndParsesWithVectorShapes() throws Exception {
        P7LogoWorkshop.Spec sample = new P7LogoWorkshop.Spec(
            "Negreco & <Droid>", "A&B <C> \"seguro\"", 0, 0);
        String svg = P7LogoSvg.build(sample);
        assertTrue(svg.startsWith("<?xml version=\"1.0\""));
        assertTrue(svg.contains("viewBox=\"0 0 1024 512\""));
        assertTrue(svg.contains("Negreco &amp; &lt;Droid&gt;"));
        assertTrue(svg.contains("A&amp;B &lt;C&gt; &quot;seguro&quot;"));
        assertFalse(svg.contains("<!DOCTYPE"));
        assertFalse(svg.contains("href="));
        assertFalse(svg.contains("width=\"1024\" height=\"512\" fill=\"#000000\""));
        XmlPullParser parser = Xml.newPullParser();
        parser.setInput(new StringReader(svg));
        int rectangles = 0, textItems = 0;
        List<String> texts = new ArrayList<>();
        int event;
        while ((event = parser.next()) != XmlPullParser.END_DOCUMENT) {
            if (event == XmlPullParser.START_TAG) {
                if ("rect".equals(parser.getName())) rectangles++;
                if ("text".equals(parser.getName())) {
                    textItems++;
                    texts.add(parser.nextText());
                }
            }
        }
        assertEquals(2, rectangles);
        assertEquals(3, textItems);
        assertTrue(texts.contains("Negreco & <Droid>"));
        assertTrue(texts.contains("A&B <C> \"seguro\""));
    }

    @Test public void oledBackgroundAndUnicodeRemainPortableXml() throws Exception {
        P7LogoWorkshop.Spec logo = new P7LogoWorkshop.Spec(
            "Marca 💠", "Edição vetorial", 2, 1);
        String svg = P7LogoSvg.build(logo);
        assertTrue(svg.contains("fill=\"#000000\""));
        assertTrue(svg.contains("fill=\"#27C99A\""));
        assertTrue(svg.contains("Marca 💠"));
        XmlPullParser parser = Xml.newPullParser();
        parser.setInput(new StringReader(svg));
        while (parser.next() != XmlPullParser.END_DOCUMENT) { }
    }

    @Test public void malformedXmlTextAndNonSafDestinationAreRejected() throws Exception {
        P7LogoWorkshop.Spec invalid = new P7LogoWorkshop.Spec(
            "N" + (char) 0xD83D, "Teste", 0, 0);
        try {
            P7LogoSvg.build(invalid);
            fail("Orphan UTF-16 surrogate cannot enter an SVG file");
        } catch (IllegalArgumentException expected) { }
        Context context = InstrumentationRegistry.getInstrumentation()
            .getTargetContext();
        try {
            P7LogoSvg.export(context,
                new P7LogoWorkshop.Spec("Seguro", "Sem APK", 0, 0),
                Uri.parse("file:///sdcard/falso.svg"));
            fail("Non-SAF output must be refused");
        } catch (java.io.IOException expected) { }
    }
}
