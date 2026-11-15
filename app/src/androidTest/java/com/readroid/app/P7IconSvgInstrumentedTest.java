package com.readroid.app;

import android.content.Context;
import android.net.Uri;
import android.util.Xml;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.StringReader;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.xmlpull.v1.XmlPullParser;
import static org.junit.Assert.*;

/** Standalone, deterministic SVG vectors backed by the native icon palette. */
@RunWith(AndroidJUnit4.class)
public final class P7IconSvgInstrumentedTest {
    private static XmlPullParser xml(String source) throws Exception {
        XmlPullParser parser = Xml.newPullParser();
        parser.setInput(new StringReader(source));
        return parser;
    }

    @Test public void allFourSymbolsUseRealEditablePathsAndParseAsXml()
            throws Exception {
        String[] expected = {"M 256 126", "M 223 199", "M 147 207", "M 256.000 138.000"};
        for (int symbol = 0; symbol < 4; symbol++) {
            String svg = P7IconSvg.build(new P7IconWorkshop.Spec(0, symbol, 0));
            assertTrue(svg.contains("viewBox=\"0 0 512 512\""));
            assertTrue(svg.contains(expected[symbol]));
            assertFalse(svg.contains("href="));
            assertFalse(svg.contains("<script"));
            assertFalse(svg.contains("<!DOCTYPE"));
            XmlPullParser parser = xml(svg);
            int paths = 0, circles = 0, rects = 0;
            while (parser.next() != XmlPullParser.END_DOCUMENT) {
                if (parser.getEventType() == XmlPullParser.START_TAG) {
                    if ("path".equals(parser.getName())) paths++;
                    if ("circle".equals(parser.getName())) circles++;
                    if ("rect".equals(parser.getName())) rects++;
                }
            }
            assertEquals(1, paths);
            assertEquals(1, circles);
            assertEquals(1, rects);
        }
    }

    @Test public void colorsAndShapesChangeActualVectorGeometry()
            throws Exception {
        String circle = P7IconSvg.build(new P7IconWorkshop.Spec(1, 1, 1));
        String square = P7IconSvg.build(new P7IconWorkshop.Spec(3, 1, 2));
        String rounded = P7IconSvg.build(new P7IconWorkshop.Spec(0, 1, 0));
        assertTrue(circle.contains("#0AAF83"));
        assertTrue(circle.contains("r=\"220\""));
        assertTrue(square.contains("#ED6C38"));
        assertTrue(square.contains("rx=\"32\""));
        assertTrue(rounded.contains("rx=\"112\""));
        assertNotEquals(circle, square);
        assertNotEquals(square, rounded);
        for (String svg : new String[]{circle, square, rounded}) {
            XmlPullParser parser = xml(svg);
            while (parser.next() != XmlPullParser.END_DOCUMENT) { }
        }
    }

    @Test public void validatesStylesAndRejectsNonSafDestination() throws Exception {
        try {
            new P7IconWorkshop.Spec(5, 0, 0);
            fail("Out-of-range palette index accepted");
        } catch (IllegalArgumentException expected) { }
        try {
            P7IconSvg.build(null);
            fail("Missing icon accepted");
        } catch (IllegalArgumentException expected) { }
        Context context = InstrumentationRegistry.getInstrumentation()
            .getTargetContext();
        try {
            P7IconSvg.export(context, new P7IconWorkshop.Spec(0, 0, 0),
                Uri.parse("file:///sdcard/unsafe.svg"));
            fail("Non-SAF URI accepted");
        } catch (java.io.IOException expected) { }
    }
}
