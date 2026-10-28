package org.opengothic.app;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import android.provider.DocumentsContract;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * Starts OpenGothic directly from a legally owned Gothic II installation
 * already present on shared storage. Game data is never copied or imported.
 */
public final class DirectFolderActivity extends Activity {
    private static final int PICK_FOLDER = 101;
    private static final String PREFS = "direct-folder";
    private static final String KEY_PATH = "gothic2-path";

    private SharedPreferences prefs;
    private TextView pathView;
    private Button play;
    private boolean waitingPermission;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        buildUi();
        refresh();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (waitingPermission && Build.VERSION.SDK_INT >= 30 && Environment.isExternalStorageManager()) {
            waitingPermission = false;
            openFolderPicker();
        }
        refresh();
    }

    private void buildUi() {
        float d = getResources().getDisplayMetrics().density;
        int pad = Math.round(24 * d);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(18, 18, 18));

        TextView title = new TextView(this);
        title.setText("OpenGothic\nGothic II: Ночь Ворона");
        title.setTextColor(Color.WHITE);
        title.setTextSize(24);
        title.setGravity(Gravity.CENTER);
        root.addView(title, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        TextView note = new TextView(this);
        note.setText("Данные игры читаются прямо из выбранной папки. Никакого ZIP-импорта и копирования.");
        note.setTextColor(Color.LTGRAY);
        note.setTextSize(15);
        note.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams np = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        np.setMargins(0, Math.round(12 * d), 0, Math.round(12 * d));
        root.addView(note, np);

        pathView = new TextView(this);
        pathView.setTextColor(Color.WHITE);
        pathView.setTextSize(14);
        pathView.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        pp.setMargins(0, pad, 0, pad);
        root.addView(pathView, pp);

        Button choose = new Button(this);
        choose.setText("Выбрать папку игры");
        choose.setOnClickListener(v -> chooseFolder());
        root.addView(choose, buttonParams(d));

        play = new Button(this);
        play.setText("Играть");
        play.setOnClickListener(v -> launchGame());
        root.addView(play, buttonParams(d));

        setContentView(root);
    }

    private LinearLayout.LayoutParams buttonParams(float d) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                Math.round(340 * d), LinearLayout.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, Math.round(8 * d), 0, 0);
        return p;
    }

    private static File child(File dir, String name) {
        File[] files = dir == null ? null : dir.listFiles();
        if (files == null)
            return null;
        for (File f : files)
            if (f.getName().equalsIgnoreCase(name))
                return f;
        return null;
    }

    private static boolean isInstallation(File dir) {
        File data = child(dir, "Data");
        File work = child(dir, "_work");
        return data != null && data.isDirectory() && work != null && work.isDirectory();
    }

    private File selected() {
        String path = prefs.getString(KEY_PATH, null);
        if (path == null || path.isEmpty())
            return null;
        File dir = new File(path);
        return isInstallation(dir) ? dir : null;
    }

    private void refresh() {
        if (pathView == null)
            return;
        File dir = selected();
        if (dir == null) {
            pathView.setText("Выберите корень Gothic II — папку, где находятся Data и _work.");
            play.setEnabled(false);
        } else {
            pathView.setText(dir.getAbsolutePath());
            play.setEnabled(true);
        }
    }

    private void chooseFolder() {
        if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            waitingPermission = true;
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                        Uri.parse("package:" + getPackageName())));
            } catch (RuntimeException e) {
                startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
            }
            return;
        }
        openFolderPicker();
    }

    private void openFolderPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                        | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(intent, PICK_FOLDER);
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != PICK_FOLDER || result != RESULT_OK || data == null || data.getData() == null)
            return;

        Uri uri = data.getData();
        try {
            getContentResolver().takePersistableUriPermission(
                    uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (SecurityException ignored) {
        }

        File dir = resolveTree(uri);
        if (dir == null) {
            message("Не удалось получить обычный путь к этой папке.");
            return;
        }
        if (!isInstallation(dir)) {
            message("Это не корень Gothic II. Нужны папки Data и _work.");
            return;
        }

        List<String> broken = GameFiles.brokenArchives(dir);
        if (!broken.isEmpty()) {
            message("Повреждён или не полностью скопирован VDF: " + broken.get(0));
            return;
        }

        try {
            prefs.edit().putString(KEY_PATH, dir.getCanonicalPath()).apply();
            message("Папка игры выбрана");
        } catch (IOException e) {
            message(e.getMessage());
        }
        refresh();
    }

    private File resolveTree(Uri uri) {
        if (Build.VERSION.SDK_INT < 30 || !DocumentsContract.isTreeUri(uri))
            return null;
        try {
            String document = DocumentsContract.getTreeDocumentId(uri);
            int colon = document.indexOf(':');
            String volumeId = colon >= 0 ? document.substring(0, colon) : document;
            String relative = colon >= 0 ? document.substring(colon + 1) : "";

            StorageManager manager = (StorageManager) getSystemService(STORAGE_SERVICE);
            for (StorageVolume volume : manager.getStorageVolumes()) {
                String id = volume.isPrimary() ? "primary" : volume.getUuid();
                if (id == null || !id.equalsIgnoreCase(volumeId))
                    continue;
                File base = volume.getDirectory();
                if (base == null)
                    return null;
                return (relative.isEmpty() ? base : new File(base, relative)).getCanonicalFile();
            }
        } catch (IOException | RuntimeException ignored) {
        }
        return null;
    }

    private void launchGame() {
        if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            chooseFolder();
            return;
        }

        File game = selected();
        File appExternal = getExternalFilesDir(null);
        if (game == null || appExternal == null) {
            refresh();
            return;
        }

        try (FileOutputStream out = new FileOutputStream(new File(appExternal, "game-path.txt"))) {
            out.write((game.getCanonicalPath() + "\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            message("Не удалось сохранить путь: " + e.getMessage());
            return;
        }

        startActivity(new Intent(this, GameActivity.class));
    }

    private void message(String text) {
        Toast.makeText(this, text == null ? "Ошибка" : text, Toast.LENGTH_LONG).show();
    }
}
