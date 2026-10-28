package org.opengothic.app;

import android.app.ActivityOptions;
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
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Minimal sideload launcher for legally owned Gothic II: Night of the Raven files.
 * It does not import or copy the game: OpenGothic reads Data/_work directly from
 * the folder selected by the user.
 */
public final class DirectFolderActivity extends AppCompatActivity {
    private static final int PICK_FOLDER = 101;
    private static final String PREFS = "direct-folder";
    private static final String KEY_PATH = "gothic2-path";

    private SharedPreferences prefs;
    private TextView pathView;
    private Button play;
    private boolean waitingPermission;

    @Override
    protected void onCreate(Bundle state) {
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
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        pathView = new TextView(this);
        pathView.setTextColor(Color.LTGRAY);
        pathView.setTextSize(14);
        pathView.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams pathParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        pathParams.setMargins(0, pad, 0, pad);
        root.addView(pathView, pathParams);

        Button choose = new Button(this);
        choose.setText("Выбрать папку игры");
        choose.setOnClickListener(v -> chooseFolder());
        root.addView(choose, buttonParams(d));

        play = new Button(this);
        play.setText("Играть");
        play.setOnClickListener(v -> play());
        root.addView(play, buttonParams(d));

        Button original = new Button(this);
        original.setText("Обычный лаунчер");
        original.setOnClickListener(v -> startActivity(new Intent(this, LauncherActivity.class)));
        root.addView(original, buttonParams(d));

        setContentView(root);
    }

    private LinearLayout.LayoutParams buttonParams(float d) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                Math.round(320 * d), LinearLayout.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, Math.round(8 * d), 0, 0);
        return p;
    }

    private File selected() {
        String path = prefs.getString(KEY_PATH, null);
        if (path == null || path.isEmpty()) return null;
        File dir = new File(path);
        return GameFiles.isInstallation(dir) ? dir : null;
    }

    private void refresh() {
        if (pathView == null) return;
        File dir = selected();
        if (dir == null) {
            pathView.setText("Выберите корень установленной игры — папку, где находятся Data и _work.");
            play.setEnabled(false);
        } else {
            pathView.setText(dir.getAbsolutePath());
            play.setEnabled(true);
        }
    }

    private void chooseFolder() {
        if (Build.VERSION.SDK_INT < 30) {
            message("Эта сборка прямого запуска рассчитана на Android 11 и новее.");
            return;
        }
        if (!Environment.isExternalStorageManager()) {
            waitingPermission = true;
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                        Uri.parse("package:" + getPackageName())));
            } catch (Exception e) {
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
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_FOLDER || resultCode != RESULT_OK || data == null || data.getData() == null) return;

        Uri uri = data.getData();
        try {
            int take = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            getContentResolver().takePersistableUriPermission(uri, take);
        } catch (SecurityException ignored) {
        }

        File dir = resolveTree(uri);
        if (dir == null) {
            message("Не удалось получить обычный путь к этой папке. Выберите папку во внутренней памяти или на SD-карте.");
            return;
        }
        if (!GameFiles.isInstallation(dir)) {
            message("Это не корень Gothic. В выбранной папке должны находиться Data и _work.");
            return;
        }
        try {
            prefs.edit().putString(KEY_PATH, dir.getCanonicalPath()).apply();
            Toast.makeText(this, "Папка Gothic II выбрана", Toast.LENGTH_LONG).show();
        } catch (IOException e) {
            message(e.getMessage());
        }
        refresh();
    }

    private File resolveTree(Uri uri) {
        if (Build.VERSION.SDK_INT < 30 || !DocumentsContract.isTreeUri(uri)) return null;
        try {
            String document = DocumentsContract.getTreeDocumentId(uri);
            int colon = document.indexOf(':');
            String volumeId = colon >= 0 ? document.substring(0, colon) : document;
            String relative = colon >= 0 ? document.substring(colon + 1) : "";

            StorageManager manager = (StorageManager) getSystemService(STORAGE_SERVICE);
            for (StorageVolume volume : manager.getStorageVolumes()) {
                String id = volume.isPrimary() ? "primary" : volume.getUuid();
                if (id == null || !id.equalsIgnoreCase(volumeId)) continue;
                File base = volume.getDirectory();
                if (base == null) return null;
                return (relative.isEmpty() ? base : new File(base, relative)).getCanonicalFile();
            }
        } catch (IOException | RuntimeException ignored) {
        }
        return null;
    }

    private void play() {
        if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            chooseFolder();
            return;
        }

        File game = selected();
        File root = Library.root(this);
        if (game == null || root == null) {
            refresh();
            return;
        }

        try {
            // OpenGothic expects this directory even if scripts ultimately come from VDF archives.
            GameFiles.ensureScriptsFolder(game);

            try (FileOutputStream out = new FileOutputStream(new File(root, "game.txt"))) {
                out.write("Gothic2\n".getBytes(StandardCharsets.UTF_8));
            }
            try (FileOutputStream out = new FileOutputStream(new File(root, "game-path.txt"))) {
                out.write((game.getCanonicalPath() + "\n").getBytes(StandardCharsets.UTF_8));
            }
        } catch (IOException e) {
            message("Не удалось подготовить запуск: " + e.getMessage());
            return;
        }

        Intent intent = new Intent(this, org.tempest.TempestNativeActivity.class);
        startActivity(intent, ActivityOptions.makeCustomAnimation(this, 0, 0).toBundle());
    }

    private void message(String text) {
        Toast.makeText(this, text == null ? "Ошибка" : text, Toast.LENGTH_LONG).show();
    }
}
