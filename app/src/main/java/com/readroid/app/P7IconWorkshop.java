package com.readroid.app;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.Button;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.ScrollView;
import java.io.IOException;
import java.io.OutputStream;

/**
 * Local-only icon workshop. Builds original artwork from Android Canvas
 * primitives, not branding, assets or content extracted from user APKs.
 * Exports a portable PNG to a destination the user explicitly chooses.
 */
public final class P7IconWorkshop {
    private static final int EXPORT_SIZE = 512;
    private static final int[] COLORS = {
        0xff096dff, 0xff0aaf83, 0xff8a4fff, 0xffed6c38, 0xff161d29
    };
    private static final String[] PALETTES = {
        "Azul", "Verde", "Violeta", "Laranja", "Grafite"
    };
    private static final String[] SYMBOLS = {"Escudo", "Código", "Pasta", "Estrela"};
    private static final String[] SHAPES = {"Arredondado", "Circular", "Quadrado"};

    /** Only three finite indices can cross Activity recreation boundaries. */
    public static final class Spec {
        public final int color;
        public final int symbol;
        public final int shape;

        public Spec(int color, int symbol, int shape) {
            if (color < 0 || color >= COLORS.length ||
                symbol < 0 || symbol >= SYMBOLS.length ||
                shape < 0 || shape >= SHAPES.length)
                throw new IllegalArgumentException("Estilo de ícone inválido");
            this.color = color;
            this.symbol = symbol;
            this.shape = shape;
        }
    }

    private P7IconWorkshop() {}

    private static int dp(Context c, int value) {
        return NegrescoTheme.dp(c, value);
    }

    private static TextView heading(Activity a, String label) {
        TextView t = new TextView(a);
        t.setText(label);
        t.setTextColor(NegrescoTheme.TEXT);
        t.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        t.setPadding(0, dp(a, 9), 0, dp(a, 4));
        return t;
    }

    private static RadioGroup choices(Activity a, LinearLayout root,
            String title, String[] names, int current,
            java.util.function.IntConsumer onSelect) {
        root.addView(heading(a, title));
        RadioGroup group = new RadioGroup(a);
        group.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < names.length; i++) {
            final int choice = i;
            RadioButton item = new RadioButton(a);
            item.setId(View.generateViewId());
            item.setButtonTintList(android.content.res.ColorStateList.valueOf(
                NegrescoTheme.ACCENT));
            item.setText(names[i]);
            item.setTextSize(10 * NegrescoTheme.FONT_SCALE);
            item.setTextColor(NegrescoTheme.TEXT);
            item.setPadding(0, 0, dp(a, 8), 0);
            item.setOnClickListener(v -> onSelect.accept(choice));
            group.addView(item);
            if (i == current) group.check(item.getId());
        }
        android.widget.HorizontalScrollView strip =
            new android.widget.HorizontalScrollView(a);
        strip.setHorizontalScrollBarEnabled(false);
        strip.addView(group);
        root.addView(strip);
        return group;
    }

    /** Native thumbnail: identical drawing pipeline to the exported PNG. */
    public static View inlinePreview(Context context, Spec spec) {
        return new Preview(context, spec);
    }

    /** Public entry point opened by either the Icons tab or its Home card. */
    public static android.app.AlertDialog open(MainActivity a) {
        return open(a, new Spec(0, 0, 0));
    }

    /** Start with a legitimate, selected catalog template. */
    public static android.app.AlertDialog open(MainActivity a, Spec initial) {
        if (initial == null) throw new IllegalArgumentException("Ícone vazio");
        final int[] state = {initial.color, initial.symbol, initial.shape};
        ScrollView scroll = new ScrollView(a);
        LinearLayout root = new LinearLayout(a);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(a, 15), dp(a, 9), dp(a, 15), dp(a, 8));
        scroll.addView(root);
        Preview preview = new Preview(a, initial);
        LinearLayout.LayoutParams previewParams = new LinearLayout.LayoutParams(
            dp(a, 145), dp(a, 145));
        previewParams.gravity = Gravity.CENTER_HORIZONTAL;
        root.addView(preview, previewParams);
        java.util.function.Consumer<Integer> color = value -> {
            state[0] = value; preview.setSpec(new Spec(state[0], state[1], state[2]));
        };
        java.util.function.Consumer<Integer> symbol = value -> {
            state[1] = value; preview.setSpec(new Spec(state[0], state[1], state[2]));
        };
        java.util.function.Consumer<Integer> shape = value -> {
            state[2] = value; preview.setSpec(new Spec(state[0], state[1], state[2]));
        };
        // Keep the primary export action inside the dialog's own scrollable
        // content, directly below the preview. System AlertDialog footer
        // buttons were missing from the accessibility tree on API 29/35.
        // This is a real button, not a label added merely for UI automation.
        Button exportButton = new Button(a);
        exportButton.setText("Exportar PNG");
        exportButton.setContentDescription("Exportar PNG 512×512");
        NegrescoTheme.styleWorkshopExport(a, exportButton, true);
        LinearLayout.LayoutParams exportParams = new LinearLayout.LayoutParams(
            -1, dp(a, 48));
        exportParams.topMargin = dp(a, 8);
        exportParams.bottomMargin = dp(a, 4);
        root.addView(exportButton, exportParams);
        Button exportSvg = new Button(a);
        exportSvg.setText("Exportar SVG");
        exportSvg.setContentDescription("Exportar SVG vetorial 512×512");
        NegrescoTheme.styleWorkshopExport(a, exportSvg, false);
        LinearLayout.LayoutParams svgParams = new LinearLayout.LayoutParams(
            -1, dp(a, 48));
        svgParams.bottomMargin = dp(a, 4);
        root.addView(exportSvg, svgParams);
        choices(a, root, "Cor", PALETTES, initial.color, color::accept);
        choices(a, root, "Símbolo", SYMBOLS, initial.symbol, symbol::accept);
        choices(a, root, "Formato", SHAPES, initial.shape, shape::accept);
        TextView note = heading(a,
            "Exporta PNG ou SVG vetorial 512×512. Não altera o ícone instalado nem arquivos do APK.");
        note.setTextSize(10 * NegrescoTheme.FONT_SCALE);
        root.addView(note);
        android.app.AlertDialog workshopDialog = new android.app.AlertDialog.Builder(a)
            .setTitle("Criador de Ícones")
            .setView(scroll)
            .setNegativeButton("Fechar", null)
            .create();
        exportButton.setOnClickListener(v -> {
            // Only a deliberate tap starts ACTION_CREATE_DOCUMENT. Closing
            // the dialog does not modify any saved preference or user APK.
            workshopDialog.dismiss();
            a.startP7IconExport(new Spec(state[0], state[1], state[2]));
        });
        exportSvg.setOnClickListener(v -> {
            P7IconWorkshop.Spec spec = new Spec(state[0], state[1], state[2]);
            workshopDialog.dismiss();
            a.startP7IconSvgExport(spec);
        });
        workshopDialog.show();
        NegrescoTheme.styleStudioDialog(workshopDialog);
        return workshopDialog;
    }

    private static class Preview extends View {
        private Spec spec;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        Preview(Context context, Spec initial) {
            super(context);
            spec = initial;
            setContentDescription("Prévia original do ícone");
        }
        void setSpec(Spec value) { spec = value; invalidate(); }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            int side = Math.min(getWidth(), getHeight());
            int save = canvas.save();
            canvas.translate((getWidth() - side) / 2f,
                (getHeight() - side) / 2f);
            canvas.scale(side / 512f, side / 512f);
            drawIcon(canvas, spec, paint);
            canvas.restoreToCount(save);
        }
    }

    static void drawIcon(Canvas canvas, Spec spec, Paint p) {
        final float inset = 36f;
        p.setShader(null);
        p.setStyle(Paint.Style.FILL);
        p.setColor(COLORS[spec.color]);
        RectF bounds = new RectF(inset, inset, 512 - inset, 512 - inset);
        if (spec.shape == 1)
            canvas.drawCircle(256, 256, 220, p);
        else
            canvas.drawRoundRect(bounds, spec.shape == 2 ? 32 : 112,
                spec.shape == 2 ? 32 : 112, p);

        p.setColor(0x30ffffff);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(6);
        canvas.drawCircle(256, 256, 153, p);

        p.setColor(Color.WHITE);
        p.setStrokeWidth(25);
        p.setStrokeJoin(Paint.Join.ROUND);
        p.setStrokeCap(Paint.Cap.ROUND);
        p.setStyle(Paint.Style.STROKE);
        Path glyph = new Path();
        switch (spec.symbol) {
            case 0: // Shield, unique original vector.
                glyph.moveTo(256, 126); glyph.lineTo(369, 166);
                glyph.lineTo(351, 298); glyph.quadTo(327, 358, 256, 393);
                glyph.quadTo(185, 358, 161, 298);
                glyph.lineTo(143, 166); glyph.close();
                canvas.drawPath(glyph, p);
                glyph.reset();
                glyph.moveTo(207, 255); glyph.lineTo(246, 294);
                glyph.lineTo(314, 221); canvas.drawPath(glyph, p);
                break;
            case 1: // Source code.
                glyph.moveTo(223, 199); glyph.lineTo(175, 256);
                glyph.lineTo(223, 313);
                glyph.moveTo(289, 199); glyph.lineTo(337, 256);
                glyph.lineTo(289, 313);
                glyph.moveTo(271, 180); glyph.lineTo(238, 332);
                canvas.drawPath(glyph, p);
                break;
            case 2: // Folder.
                glyph.moveTo(147, 207); glyph.lineTo(203, 207);
                glyph.lineTo(228, 182); glyph.lineTo(365, 182);
                glyph.lineTo(365, 326); glyph.lineTo(147, 326);
                glyph.close(); canvas.drawPath(glyph, p);
                break;
            case 3: // Star, filled.
                p.setStyle(Paint.Style.FILL);
                for (int i = 0; i < 10; i++) {
                    double angle = -Math.PI / 2 + i * Math.PI / 5;
                    float radius = i % 2 == 0 ? 118 : 49;
                    float x = 256 + (float) Math.cos(angle) * radius;
                    float y = 256 + (float) Math.sin(angle) * radius;
                    if (i == 0) glyph.moveTo(x, y);
                    else glyph.lineTo(x, y);
                }
                glyph.close(); canvas.drawPath(glyph, p);
                break;
            default: throw new IllegalArgumentException("Símbolo inválido");
        }
        p.setStyle(Paint.Style.FILL);
    }

    /** No storage permissions. Caller must provide a SAF document URI. */
    public static void export(Context context, Spec spec, Uri destination)
            throws IOException {
        if (spec == null || destination == null ||
                !"content".equals(destination.getScheme()))
            throw new IOException("Destino de exportação não autorizado");
        Bitmap bitmap = Bitmap.createBitmap(EXPORT_SIZE, EXPORT_SIZE,
            Bitmap.Config.ARGB_8888);
        try {
            Canvas canvas = new Canvas(bitmap);
            drawIcon(canvas, spec, new Paint(Paint.ANTI_ALIAS_FLAG));
            try (OutputStream stream =
                    context.getContentResolver().openOutputStream(destination, "w")) {
                if (stream == null || !bitmap.compress(
                        Bitmap.CompressFormat.PNG, 100, stream))
                    throw new IOException("Não foi possível gravar o ícone");
                stream.flush();
            }
        } finally {
            bitmap.recycle();
        }
    }
}
