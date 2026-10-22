package com.readroid.app;

import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.net.Uri;
import android.text.Editable;
import android.text.InputFilter;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.IOException;
import java.io.OutputStream;

/**
 * Self-contained logo designer. Input never modifies the installed app, an APK,
 * the saved identity or a project's pending edit plan.
 */
public final class P7LogoWorkshop {
    static final int WIDTH = 1024;
    static final int HEIGHT = 512;
    private static final int[] ACCENTS = {
        0xff1688ff, 0xff9b6dff, 0xff27c99a, 0xffffa24a
    };
    private static final String[] COLORS = {"Azul", "Violeta", "Verde", "Laranja"};
    private static final String[] BACKGROUNDS = {"Transparente", "OLED preto"};

    /** Immutable, bounded export input; no arbitrary files or bitmap sources. */
    public static final class Spec {
        public final String name;
        public final String subtitle;
        public final int color;
        public final int background;

        public Spec(String name, String subtitle, int color, int background) {
            if (name == null || subtitle == null || name.trim().isEmpty()
                    || name.length() > 30 || subtitle.length() > 48
                    || containsControl(name) || containsControl(subtitle)
                    || color < 0 || color >= ACCENTS.length
                    || background < 0 || background >= BACKGROUNDS.length)
                throw new IllegalArgumentException("Texto ou estilo de logo inválido");
            this.name = name.trim();
            this.subtitle = subtitle.trim();
            this.color = color;
            this.background = background;
        }
    }

    private P7LogoWorkshop() {}

    /** Shared color mapping for PNG Canvas and editable SVG exports. */
    static int accentColor(Spec spec) {
        if (spec == null) throw new IllegalArgumentException("Logo vazio");
        return ACCENTS[spec.color];
    }

    private static boolean containsControl(String text) {
        for (int i = 0; i < text.length(); i++)
            if (Character.isISOControl(text.charAt(i))) return true;
        return false;
    }

    private static int dp(Context context, int size) {
        return NegrescoTheme.dp(context, size);
    }

    private static Spec currentIdentity(Context c) {
        SharedPreferences prefs = c.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        String name = prefs.getString("display_name", "NegrecoDroid");
        String subtitle = prefs.getString("display_subtitle", "APK ENGINEERING STUDIO");
        try {
            return new Spec(name, subtitle, 0, 0);
        } catch (IllegalArgumentException invalidPreference) {
            // Untrusted/corrupt legacy settings must not crash the editor.
            return new Spec("NegrecoDroid", "APK ENGINEERING STUDIO", 0, 0);
        }
    }

    private static TextView caption(Context context, String text) {
        TextView view = new TextView(context);
        view.setText(text);
        view.setTextColor(NegrescoTheme.TEXT);
        view.setTextSize(12 * NegrescoTheme.FONT_SCALE);
        view.setPadding(0, dp(context, 10), 0, dp(context, 4));
        return view;
    }

    private static RadioGroup options(MainActivity a, LinearLayout root,
            String title, String[] values, int current,
            java.util.function.IntConsumer selected) {
        root.addView(caption(a, title));
        RadioGroup group = new RadioGroup(a);
        group.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < values.length; i++) {
            final int index = i;
            RadioButton option = new RadioButton(a);
            option.setId(View.generateViewId());
            option.setText(values[i]);
            option.setTextColor(NegrescoTheme.TEXT);
            option.setTextSize(11 * NegrescoTheme.FONT_SCALE);
            option.setButtonTintList(ColorStateList.valueOf(NegrescoTheme.ACCENT));
            option.setPadding(0, 0, dp(a, 12), 0);
            option.setOnClickListener(v -> selected.accept(index));
            group.addView(option);
            if (i == current) group.check(option.getId());
        }
        HorizontalScrollView horizontal = new HorizontalScrollView(a);
        horizontal.setHorizontalScrollBarEnabled(false);
        horizontal.addView(group);
        root.addView(horizontal);
        return group;
    }

    private static final class Preview extends View {
        private Spec spec;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

        Preview(Context context, Spec first) {
            super(context);
            spec = first;
            setContentDescription("Prévia original do logo");
            // Preview alone shows a checkerboard for transparent output.
            // The exported bitmap is never composited against this pattern.
        }

        void setSpec(Spec updated) {
            spec = updated;
            invalidate();
        }

        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float scale = Math.min(getWidth() / (float) WIDTH,
                                   getHeight() / (float) HEIGHT);
            if (scale <= 0) return;
            int saved = canvas.save();
            canvas.translate((getWidth() - WIDTH * scale) / 2f,
                (getHeight() - HEIGHT * scale) / 2f);
            canvas.scale(scale, scale);
            if (spec.background == 0) {
                // Checkerboard is a preview affordance, never embedded in PNG.
                paint.reset();
                paint.setStyle(Paint.Style.FILL);
                canvas.drawColor(0xff111720);
                for (int y = 0; y < HEIGHT; y += 48) {
                    for (int x = 0; x < WIDTH; x += 48) {
                        if (((x / 48) + (y / 48)) % 2 == 0) {
                            paint.setColor(0xff263242);
                            canvas.drawRect(x, y, Math.min(x + 48, WIDTH),
                                Math.min(y + 48, HEIGHT), paint);
                        }
                    }
                }
            }
            drawLogo(canvas, spec, paint);
            canvas.restoreToCount(saved);
        }
    }

    private static void updatePreview(Preview view, EditText name,
            EditText subtitle, int[] options) {
        try {
            view.setSpec(new Spec(name.getText().toString(),
                subtitle.getText().toString(), options[0], options[1]));
        } catch (IllegalArgumentException invalidWhileTyping) {
            // Keep the last valid artwork visible while the user types.
        }
    }

    public static AlertDialog open(MainActivity activity) {
        final Spec initial = currentIdentity(activity);
        final int[] selected = {initial.color, initial.background};
        // A fixed-height scroll region leaves the real export button visible
        // as an always-accessible footer on compact Android screens.
        LinearLayout dialogBody = new LinearLayout(activity);
        dialogBody.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll = new ScrollView(activity);
        int screenHeight = activity.getResources().getDisplayMetrics().heightPixels;
        int scrollHeight = Math.min(dp(activity, 360),
            Math.max(dp(activity, 180), screenHeight - dp(activity, 290)));
        dialogBody.addView(scroll, new LinearLayout.LayoutParams(-1, scrollHeight));
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(activity, 16), dp(activity, 10),
                        dp(activity, 16), dp(activity, 10));
        root.setFocusableInTouchMode(true);
        scroll.addView(root);

        Preview preview = new Preview(activity, initial);
        root.addView(preview, new LinearLayout.LayoutParams(-1, dp(activity, 174)));

        root.addView(caption(activity, "Nome do logo"));
        EditText name = new EditText(activity);
        name.setSingleLine(true);
        name.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_FLAG_CAP_WORDS);
        name.setFilters(new InputFilter[]{new InputFilter.LengthFilter(30)});
        name.setText(initial.name);
        name.setSelectAllOnFocus(true);
        name.setContentDescription("Nome do logo");
        name.setTextColor(NegrescoTheme.TEXT);
        name.setTextSize(15 * NegrescoTheme.FONT_SCALE);
        root.addView(name);

        root.addView(caption(activity, "Subtítulo do logo"));
        EditText subtitle = new EditText(activity);
        subtitle.setSingleLine(true);
        subtitle.setFilters(new InputFilter[]{new InputFilter.LengthFilter(48)});
        subtitle.setText(initial.subtitle);
        subtitle.setContentDescription("Subtítulo do logo");
        subtitle.setTextColor(NegrescoTheme.TEXT);
        subtitle.setTextSize(13 * NegrescoTheme.FONT_SCALE);
        root.addView(subtitle);

        TextWatcher onEdit = new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start,
                int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start,
                int before, int count) {
                updatePreview(preview, name, subtitle, selected);
            }
            @Override public void afterTextChanged(Editable value) {}
        };
        name.addTextChangedListener(onEdit);
        subtitle.addTextChangedListener(onEdit);

        options(activity, root, "Cor de destaque", COLORS, selected[0], value -> {
            selected[0] = value;
            updatePreview(preview, name, subtitle, selected);
        });
        options(activity, root, "Fundo do PNG", BACKGROUNDS,
            selected[1], value -> {
                selected[1] = value;
                updatePreview(preview, name, subtitle, selected);
            });

        Button export = new Button(activity);
        export.setText("Exportar logo PNG");
        export.setAllCaps(false);
        export.setContentDescription("Exportar logo PNG 1024×512");
        export.setTextColor(NegrescoTheme.ON_ACCENT);
        export.setBackgroundTintList(ColorStateList.valueOf(NegrescoTheme.ACCENT));
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
            -1, dp(activity, 48));
        buttonParams.topMargin = dp(activity, 12);
        buttonParams.leftMargin = dp(activity, 16);
        buttonParams.rightMargin = dp(activity, 16);
        dialogBody.addView(export, buttonParams);

        Button exportSvg = new Button(activity);
        exportSvg.setText("Exportar logo SVG");
        exportSvg.setAllCaps(false);
        exportSvg.setContentDescription("Exportar logo SVG vetorial");
        exportSvg.setTextColor(NegrescoTheme.ON_ACCENT);
        exportSvg.setBackgroundTintList(ColorStateList.valueOf(NegrescoTheme.ACCENT));
        LinearLayout.LayoutParams svgParams = new LinearLayout.LayoutParams(
            -1, dp(activity, 48));
        svgParams.leftMargin = dp(activity, 16);
        svgParams.rightMargin = dp(activity, 16);
        svgParams.topMargin = dp(activity, 4);
        dialogBody.addView(exportSvg, svgParams);

        TextView warning = caption(activity,
            "Exportação local. Não altera o nome salvo, o APK nem o ícone instalado.");
        warning.setTextColor(NegrescoTheme.MUTED);
        warning.setTextSize(10 * NegrescoTheme.FONT_SCALE);
        root.addView(warning);

        AlertDialog dialog = new AlertDialog.Builder(activity)
            .setTitle("Criador de Logos")
            .setView(dialogBody)
            .setNegativeButton("Fechar", null)
            .create();
        export.setOnClickListener(v -> {
            try {
                Spec spec = new Spec(name.getText().toString(),
                    subtitle.getText().toString(), selected[0], selected[1]);
                dialog.dismiss();
                activity.startP7LogoExport(spec);
            } catch (IllegalArgumentException invalid) {
                name.setError("Informe um nome válido para exportar");
            }
        });
        exportSvg.setOnClickListener(v -> {
            try {
                Spec spec = new Spec(name.getText().toString(),
                    subtitle.getText().toString(), selected[0], selected[1]);
                // Fail before asking the user to create a file on invalid XML.
                P7LogoSvg.build(spec);
                dialog.dismiss();
                activity.startP7LogoSvgExport(spec);
            } catch (IllegalArgumentException invalid) {
                name.setError("Texto incompatível com SVG");
            }
        });
        root.requestFocus();
        dialog.show();
        if (dialog.getWindow() != null)
            dialog.getWindow().setSoftInputMode(
                WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
        return dialog;
    }

    /** Pure Android Canvas renderer, shared by the preview and PNG export. */
    static void drawLogo(Canvas canvas, Spec spec, Paint paint) {
        paint.reset();
        paint.setAntiAlias(true);
        paint.setStyle(Paint.Style.FILL);
        if (spec.background == 1) {
            // OLED means true, opaque #000000 across the entire PNG canvas.
            // No translucent corner pixels or navy tint.
            canvas.drawColor(Color.BLACK);
        }
        int accent = ACCENTS[spec.color];
        paint.setColor(accent);
        canvas.drawRoundRect(new RectF(72, 142, 250, 320), 52, 52, paint);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(android.graphics.Typeface.create(
            android.graphics.Typeface.DEFAULT,
            android.graphics.Typeface.BOLD));
        paint.setColor(Color.WHITE);
        paint.setTextSize(106);
        String letter = spec.name.substring(
            0, spec.name.offsetByCodePoints(0, 1)).toUpperCase(java.util.Locale.ROOT);
        canvas.drawText(letter, 161, 263, paint);

        paint.setTextAlign(Paint.Align.LEFT);
        paint.setColor(accent);
        paint.setTextSize(76);
        float titleWidth = paint.measureText(spec.name);
        if (titleWidth > 666f)
            paint.setTextSize(76f * 666f / titleWidth);
        canvas.drawText(spec.name, 295, 240, paint);

        paint.setColor(0xff9aafc8);
        paint.setTypeface(android.graphics.Typeface.DEFAULT);
        paint.setTextSize(31);
        float subtitleWidth = paint.measureText(spec.subtitle);
        if (subtitleWidth > 670f)
            paint.setTextSize(31f * 670f / subtitleWidth);
        canvas.drawText(spec.subtitle, 299, 305, paint);

        paint.setStrokeWidth(5);
        paint.setColor(accent);
        canvas.drawRoundRect(new RectF(296, 352, 760, 357), 2, 2, paint);
    }

    /** User explicitly chooses destination through ACTION_CREATE_DOCUMENT. */
    public static void export(Context context, Spec spec, Uri destination)
            throws IOException {
        if (context == null || spec == null || destination == null
                || !"content".equals(destination.getScheme()))
            throw new IOException("Destino de exportação não autorizado");
        Bitmap bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888);
        try {
            drawLogo(new Canvas(bitmap), spec, new Paint(Paint.ANTI_ALIAS_FLAG));
            try (OutputStream output = context.getContentResolver()
                    .openOutputStream(destination, "w")) {
                if (output == null
                        || !bitmap.compress(Bitmap.CompressFormat.PNG, 100, output))
                    throw new IOException("Não foi possível gravar o logo");
                output.flush();
            }
        } finally {
            bitmap.recycle();
        }
    }
}
