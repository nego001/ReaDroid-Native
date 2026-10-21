package com.readroid.app;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Experimental read-only archive catalog stored on disk. SQLite pages replace
 * a second in-memory JSON listing; this does not unlock the APK import limit.
 *
 * Build only from an already-approved private-cache archive, off the UI thread.
 * Input bytes and ZIP contents are never extracted or modified.
 */
public final class ApkDiskIndex {
    private static final int MAX_ENTRIES = 150000;
    private static final int MAX_PATH_CHARS = 4096;
    private static final int MAX_DEPTH = 128;
    private static final int MAX_PAGE = 120;
    private static final long MAX_ENTRY_BYTES = 1073741824L;
    private static final long MAX_TOTAL_BYTES = 2147483648L;
    private static final long MAX_INDEX_BYTES = 128L * 1024 * 1024;

    private ApkDiskIndex() {}

    public static final class Stats {
        public final int files;
        public final int directories;
        public final long totalUncompressedBytes;
        public final long databaseBytes;

        Stats(int files, int directories, long totalUncompressedBytes, long databaseBytes) {
            this.files = files;
            this.directories = directories;
            this.totalUncompressedBytes = totalUncompressedBytes;
            this.databaseBytes = databaseBytes;
        }
    }

    public static final class Item {
        public final String path;
        public final String name;
        public final String category;
        public final boolean directory;
        public final long sizeBytes;

        Item(String path, String name, String category, boolean directory, long sizeBytes) {
            this.path = path;
            this.name = name;
            this.category = category;
            this.directory = directory;
            this.sizeBytes = sizeBytes;
        }
    }

    public static final class Page {
        public final List<Item> items;
        public final int totalMatches;
        public final int offset;

        Page(List<Item> items, int totalMatches, int offset) {
            this.items = Collections.unmodifiableList(items);
            this.totalMatches = totalMatches;
            this.offset = offset;
        }
    }

    /**
     * Creates a new index for one ZIP; refuses existing destinations to avoid
     * modifying a previous project's data. A failed build deletes its index.
     */
    public static Stats build(File archive, File indexFile) throws IOException {
        if (archive == null || !archive.isFile() || indexFile == null)
            throw new IOException("Arquivo ou destino de índice inválido");
        if (indexFile.exists())
            throw new IOException("Destino de índice já existe");
        if (archive.getCanonicalPath().equals(indexFile.getCanonicalPath()))
            throw new IOException("Não é permitido indexar sobre o original");
        SQLiteDatabase db = null;
        int files = 0;
        int dirs = 0;
        long uncompressed = 0;
        boolean finished = false;
        try {
            db = SQLiteDatabase.openOrCreateDatabase(indexFile, null);
            db.execSQL("PRAGMA cache_size = -2048");
            int pageSize = pragmaInteger(db, "page_size");
            if (pageSize <= 0) throw new IOException("Tamanho de página SQLite inválido");
            // PRAGMA max_page_count returns a row; Android SQLiteDatabase.execSQL
            // refuses it even when used as an assignment. setMaximumSize()
            // applies the quota through Android's supported SQLite API.
            long maximum = db.setMaximumSize(MAX_INDEX_BYTES);
            if (maximum < pageSize || maximum > MAX_INDEX_BYTES + pageSize)
                throw new IOException("Cota do índice SQLite não aplicada");
            db.execSQL("CREATE TABLE entries ("
                + "path TEXT PRIMARY KEY NOT NULL,"
                + "parent TEXT NOT NULL, name TEXT NOT NULL,"
                + "is_dir INTEGER NOT NULL, explicit INTEGER NOT NULL,"
                + "size_bytes INTEGER NOT NULL, category TEXT NOT NULL)");
            db.execSQL("CREATE INDEX browse_parent ON entries"
                + "(parent, is_dir DESC, name COLLATE NOCASE)");
            db.execSQL("CREATE TABLE meta (source_bytes INTEGER NOT NULL,"
                + "source_modified INTEGER NOT NULL)");
            ContentValues meta = new ContentValues();
            meta.put("source_bytes", archive.length());
            meta.put("source_modified", archive.lastModified());
            db.insertOrThrow("meta", null, meta);

            try (ZipFile zip = new ZipFile(archive)) {
                Enumeration<? extends ZipEntry> entries = zip.entries();
                int seen = 0;
                db.beginTransaction();
                try {
                    while (entries.hasMoreElements()) {
                        if (Thread.currentThread().isInterrupted())
                            throw new java.io.InterruptedIOException("Indexação cancelada");
                        ZipEntry entry = entries.nextElement();
                        if (++seen > MAX_ENTRIES)
                            throw new IOException("Arquivo ZIP excede 150 mil entradas");
                        String path = entry.getName();
                        validatePath(path);
                        boolean dir = entry.isDirectory();
                        long size = entry.getSize();
                        if (!dir) {
                            if (size > MAX_ENTRY_BYTES)
                                throw new IOException("Entrada maior que 1 GiB");
                            if (size > 0) {
                                if (uncompressed > MAX_TOTAL_BYTES - size)
                                    throw new IOException("Total descompactado excede 2 GiB");
                                uncompressed += size;
                            }
                            files++;
                        } else {
                            dirs++;
                        }
                        int slash = path.indexOf('/');
                        while (slash >= 0 && slash < path.length() - 1) {
                            putImplicitDirectory(db, path.substring(0, slash + 1));
                            slash = path.indexOf('/', slash + 1);
                        }
                        putExplicit(db, path, dir, dir ? 0 : size);
                        if ((seen % 256) == 0) {
                            db.setTransactionSuccessful();
                            db.endTransaction();
                            db.beginTransaction();
                        }
                    }
                    db.setTransactionSuccessful();
                } finally {
                    if (db.inTransaction()) db.endTransaction();
                }
            }
            // Detect changes during the index build. Not a cryptographic source
            // identity check; the private workspace will own the cache file.
            try (Cursor m = db.rawQuery("SELECT source_bytes, source_modified FROM meta", null)) {
                if (!m.moveToFirst() || m.getLong(0) != archive.length()
                        || m.getLong(1) != archive.lastModified())
                    throw new IOException("Origem mudou durante a indexação");
            }
            db.close();
            db = null;
            if (indexFile.length() > MAX_INDEX_BYTES)
                throw new IOException("Índice acima do limite de armazenamento");
            finished = true;
            return new Stats(files, dirs, uncompressed, indexFile.length());
        } catch (android.database.SQLException invalid) {
            throw new IOException("Índice SQLite indisponível ou corrompido", invalid);
        } finally {
            if (db != null && db.isOpen()) db.close();
            if (!finished) SQLiteDatabase.deleteDatabase(indexFile);
        }
    }

    /**
     * Returns at most 120 rows; only metadata is loaded from SQLite.
     * An empty search shows direct children. Nonempty search is global.
     */
    public static Page page(File archive, File indexFile, String folder,
            String search, String category, int offset, int limit) throws IOException {
        if (archive == null || !archive.isFile() || indexFile == null || !indexFile.isFile())
            throw new IOException("Arquivo ou índice não encontrado");
        if (offset < 0 || limit < 1 || limit > MAX_PAGE)
            throw new IOException("Paginação fora dos limites");
        String directory = folder == null ? "" : folder;
        if (!directory.isEmpty()) {
            validatePath(directory);
            if (!directory.endsWith("/"))
                throw new IOException("Pasta deve terminar com /");
        }
        String query = search == null ? "" : search.trim();
        if (query.length() > 256) throw new IOException("Busca excessivamente longa");
        String filter = category == null ? "Todos" : category;
        if (filter.length() > 80) throw new IOException("Filtro inválido");

        SQLiteDatabase db = null;
        try {
            db = SQLiteDatabase.openDatabase(indexFile.getPath(), null,
                SQLiteDatabase.OPEN_READONLY);
            try (Cursor meta = db.rawQuery(
                    "SELECT source_bytes, source_modified FROM meta", null)) {
                if (!meta.moveToFirst() || meta.getLong(0) != archive.length()
                        || meta.getLong(1) != archive.lastModified())
                    throw new IOException("Índice pertence a outra versão do arquivo");
            }
            List<String> args = new ArrayList<>();
            StringBuilder where = new StringBuilder();
            if (query.isEmpty()) {
                where.append("parent = ?");
                args.add(directory);
            } else {
                where.append("is_dir = 0 AND instr(lower(path), lower(?)) > 0");
                args.add(query);
            }
            if ("Smali".equals(filter)) {
                where.append(" AND (is_dir = 1 OR lower(path) LIKE '%.smali')");
            } else if ("XML".equals(filter)) {
                where.append(" AND (is_dir = 1 OR lower(path) LIKE '%.xml')");
            } else if ("Imagens".equals(filter)) {
                where.append(" AND (is_dir = 1 OR lower(path) LIKE '%.png'"
                    + " OR lower(path) LIKE '%.webp' OR lower(path) LIKE '%.jpg'"
                    + " OR lower(path) LIKE '%.jpeg' OR lower(path) LIKE '%.gif'"
                    + " OR lower(path) LIKE '%.bmp')");
            } else if (!"Todos".equals(filter)) {
                where.append(" AND (is_dir = 1 OR category = ?)");
                args.add(filter);
            }
            String[] params = args.toArray(new String[0]);
            int total;
            try (Cursor count = db.rawQuery(
                    "SELECT count(*) FROM entries WHERE " + where, params)) {
                if (!count.moveToFirst()) throw new IOException("Índice sem contagem");
                total = count.getInt(0);
            }
            args.add(Integer.toString(limit));
            args.add(Integer.toString(offset));
            List<Item> items = new ArrayList<>(Math.min(MAX_PAGE, limit));
            try (Cursor rows = db.rawQuery(
                    "SELECT path,name,category,is_dir,size_bytes FROM entries WHERE "
                        + where + " ORDER BY is_dir DESC, name COLLATE NOCASE, path"
                        + " LIMIT ? OFFSET ?", args.toArray(new String[0]))) {
                while (rows.moveToNext())
                    items.add(new Item(rows.getString(0), rows.getString(1),
                        rows.getString(2), rows.getInt(3) == 1, rows.getLong(4)));
            }
            return new Page(items, total, offset);
        } catch (android.database.SQLException invalid) {
            throw new IOException("Falha ao consultar índice SQLite", invalid);
        } finally {
            if (db != null && db.isOpen()) db.close();
        }
    }

    /**
     * Checks a retained directory against the real indexed archive. The
     * "entries" table includes explicit and inferred directories, so this
     * works even when that folder is absent from the limited JSON fallback.
     * A stale/corrupt index is never accepted as authority for navigation.
     */
    static boolean containsDirectory(File archive, File indexFile, String directory)
            throws IOException {
        if (archive == null || !archive.isFile() || indexFile == null
                || !indexFile.isFile() || directory == null
                || !directory.endsWith("/"))
            throw new IOException("Diretório ou índice indisponível");
        validatePath(directory);
        SQLiteDatabase db = null;
        try {
            db = SQLiteDatabase.openDatabase(indexFile.getPath(), null,
                SQLiteDatabase.OPEN_READONLY);
            try (Cursor meta = db.rawQuery(
                    "SELECT source_bytes, source_modified FROM meta", null)) {
                if (!meta.moveToFirst() || meta.getLong(0) != archive.length()
                        || meta.getLong(1) != archive.lastModified())
                    throw new IOException("Índice pertence a outra versão do arquivo");
            }
            try (Cursor found = db.rawQuery(
                    "SELECT is_dir FROM entries WHERE path = ? LIMIT 1",
                    new String[]{directory})) {
                return found.moveToFirst() && found.getInt(0) == 1;
            }
        } catch (android.database.SQLException invalid) {
            throw new IOException("Falha ao validar pasta no índice", invalid);
        } finally {
            if (db != null && db.isOpen()) db.close();
        }
    }

    private static int pragmaInteger(SQLiteDatabase db, String name) throws IOException {
        try (Cursor value = db.rawQuery("PRAGMA " + name, null)) {
            if (!value.moveToFirst()) throw new IOException("PRAGMA SQLite indisponível");
            return value.getInt(0);
        }
    }

    private static void putImplicitDirectory(SQLiteDatabase db, String path)
            throws IOException {
        ContentValues item = row(path, true, 0, 0);
        db.insertWithOnConflict("entries", null, item, SQLiteDatabase.CONFLICT_IGNORE);
    }

    private static void putExplicit(SQLiteDatabase db, String path, boolean dir,
            long bytes) throws IOException {
        if (dir) {
            ContentValues mark = new ContentValues();
            mark.put("explicit", 1);
            if (db.update("entries", mark,
                    "path = ? AND is_dir = 1 AND explicit = 0", new String[]{path}) == 1)
                return;
        }
        db.insertOrThrow("entries", null, row(path, dir, 1, bytes));
    }

    private static ContentValues row(String path, boolean dir, int explicit,
            long bytes) {
        String trimmed = dir ? path.substring(0, path.length() - 1) : path;
        int slash = trimmed.lastIndexOf('/');
        String parent = slash < 0 ? "" : trimmed.substring(0, slash + 1);
        String name = trimmed.substring(slash + 1) + (dir ? "/" : "");
        ContentValues values = new ContentValues();
        values.put("path", path);
        values.put("parent", parent);
        values.put("name", name);
        values.put("is_dir", dir ? 1 : 0);
        values.put("explicit", explicit);
        values.put("size_bytes", bytes);
        values.put("category", dir ? "Pasta" : ApkExplorer.category(path));
        return values;
    }

    // Package-private for platform-independent path-security regression tests.
    static void validatePath(String path) throws IOException {
        if (path == null || path.isEmpty() || path.length() > MAX_PATH_CHARS
                || path.startsWith("/") || path.indexOf('\\') >= 0
                || path.indexOf(0) >= 0)
            throw new IOException("Caminho ZIP inseguro ou grande demais");
        String[] segments = path.split("/", -1);
        if (segments.length > MAX_DEPTH + 1)
            throw new IOException("Profundidade excessiva de diretórios");
        for (int i = 0; i < segments.length; i++) {
            if (segments[i].isEmpty() && i == segments.length - 1) continue;
            if (segments[i].isEmpty() || ".".equals(segments[i])
                    || "..".equals(segments[i]))
                throw new IOException("Caminho ZIP potencialmente inseguro");
        }
    }
}
