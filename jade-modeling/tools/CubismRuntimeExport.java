package jade.export;

import com.live2d.cubism.CEAppCtrl;
import com.live2d.cubism.CECubismEditorApp;
import com.live2d.cubism.doc.IDocument;
import com.live2d.cubism.doc.model.CModelSource;
import com.live2d.cubism.doc.model.exporter.CModelExportSettingDialogData;
import com.live2d.cubism.doc.model.exporter.b;
import com.live2d.cubism.doc.model.exporter.di;
import com.live2d.cubism.doc.modeling.CModelingDocument;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;
import kotlin.Pair;

/** Version-locked Runtime export bridge for Live2D Cubism Editor 5.2.03. */
public final class CubismRuntimeExport {
    private static final long LOAD_TIMEOUT_MS = 180_000L;

    private CubismRuntimeExport() {}

    public static void main(String[] args) {
        int exitCode = 0;
        try {
            run(args);
        } catch (Throwable error) {
            exitCode = 2;
            error.printStackTrace(System.err);
        } finally {
            System.out.flush();
            System.err.flush();
            System.exit(exitCode);
        }
    }

    private static void run(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("usage: CubismRuntimeExport <source.cmo3> <output-dir>");
        }
        Path sourceFile = Path.of(args[0]).toAbsolutePath().normalize();
        Path outputDir = Path.of(args[1]).toAbsolutePath().normalize();
        if (!Files.isRegularFile(sourceFile)) {
            throw new IllegalArgumentException("CMO3 missing: " + sourceFile);
        }
        Files.createDirectories(outputDir);

        CECubismEditorApp.main(new String[] {sourceFile.toString()});
        CModelSource source = waitForModel();
        source.getTextureManager().changeModelTextureInput_toAtlas();

        b exporter = new b();
        CModelExportSettingDialogData setting = exporter.a();
        setting.setup(source);
        setting.setVersion(CModelExportSettingDialogData.FormatVersion.VERSION_50);
        setting.setEnableExtendEdgeColor(true);
        setting.setPixelsPerUnit(Math.min(source.getCanvas().getPixelWidth(), source.getCanvas().getPixelHeight()));
        di mocResult = b.a(exporter, source, null);
        if (mocResult == null || mocResult.a().isEmpty()) {
            throw new IllegalStateException("Cubism returned an empty moc3 result");
        }

        Class<?> companionClass = Class.forName("com.live2d.cubism.doc.model.exporter.b$a");
        Class<?> targetClass = Class.forName("com.live2d.cubism.doc.model.exporter.b$b");
        Object companion = b.class.getField("a").get(null);
        @SuppressWarnings({"rawtypes", "unchecked"})
        Object sdk = Enum.valueOf((Class) targetClass, "SDK");
        Method writeModelData = companionClass.getDeclaredMethod(
                "a", companionClass, String.class, CModelSource.class, di.class,
                setting.getVersion().b().getClass(), int.class,
                boolean.class, boolean.class, boolean.class, boolean.class,
                boolean.class, boolean.class, boolean.class, targetClass);
        writeModelData.setAccessible(true);
        @SuppressWarnings("unchecked")
        List<Pair<String, byte[]>> files = (List<Pair<String, byte[]>>) writeModelData.invoke(
                null, companion, "Jade", source, mocResult, setting.getVersion().b(), 1,
                false, false, false, false, true, false, true, sdk);
        if (files == null || files.isEmpty()) {
            throw new IllegalStateException("Cubism returned an empty Runtime package");
        }

        for (Pair<String, byte[]> entry : files) {
            Path destination = outputDir.resolve(entry.getFirst()).normalize();
            if (!destination.startsWith(outputDir) || destination.equals(outputDir)) {
                throw new IllegalStateException("unsafe Runtime path: " + entry.getFirst());
            }
            Files.createDirectories(destination.getParent());
            Path temporary = destination.resolveSibling(destination.getFileName() + ".tmp-export");
            Files.write(temporary, entry.getSecond());
            try {
                Files.move(temporary, destination, StandardCopyOption.REPLACE_EXISTING,
                        StandardCopyOption.ATOMIC_MOVE);
            } catch (java.nio.file.AtomicMoveNotSupportedException ignored) {
                Files.move(temporary, destination, StandardCopyOption.REPLACE_EXISTING);
            }
            System.out.println(entry.getFirst() + "\t" + entry.getSecond().length);
        }
        System.out.println("CUBISM_RUNTIME_EXPORT_OK files=" + files.size() + " output=" + outputDir);
    }

    private static CModelSource waitForModel() throws Exception {
        long deadline = System.currentTimeMillis() + LOAD_TIMEOUT_MS;
        while (System.currentTimeMillis() < deadline) {
            CEAppCtrl controller = CECubismEditorApp.a.a();
            if (controller != null) {
                IDocument document = controller.getCompletePack().getCurrentDoc();
                if (document instanceof CModelingDocument) {
                    CModelSource source = ((CModelingDocument) document).getModelSource();
                    if (source != null && !source.getAllArtMeshes().isEmpty()) {
                        Thread.sleep(750L);
                        return source;
                    }
                }
            }
            Thread.sleep(250L);
        }
        throw new IllegalStateException("Cubism did not finish loading the CMO3 within the timeout");
    }
}
