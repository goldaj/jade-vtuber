package jade.export;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import javax.swing.SwingUtilities;

/**
 * Headless-ish bridge to Cubism Editor's own 5.2.03 runtime exporter.
 *
 * <p>The Editor is still started normally so its document loader and native
 * runtime are initialized.  Once the requested CMO3 is loaded, the exact same
 * internal exporter used by "Export for Runtime" is called through reflection.
 * No Cubism installation files are changed.</p>
 */
public final class CubismExportRunner {
    private static final long LOAD_TIMEOUT_MS = 180_000L;

    private CubismExportRunner() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException(
                    "usage: CubismExportRunner <source.cmo3> <output-directory>");
        }

        Path sourcePath = Path.of(args[0]).toAbsolutePath().normalize();
        Path outputDirectory = Path.of(args[1]).toAbsolutePath().normalize();
        if (!Files.isRegularFile(sourcePath)) {
            throw new IllegalArgumentException("CMO3 does not exist: " + sourcePath);
        }
        Files.createDirectories(outputDirectory);

        AtomicReference<Throwable> startupFailure = new AtomicReference<>();
        Thread editorThread = new Thread(() -> {
            try {
                Class<?> appClass = Class.forName("com.live2d.cubism.CECubismEditorApp");
                Method main = appClass.getMethod("main", String[].class);
                // Cubism 5.2.03's public main entry does not reliably consume
                // a direct CMO3 path when another Editor instance is already
                // running.  Start the temporary exporter normally, then use
                // CEAppCtrl.command_open explicitly on the EDT below.
                main.invoke(null, (Object) new String[] {""});
            } catch (InvocationTargetException error) {
                startupFailure.set(error.getTargetException());
            } catch (Throwable error) {
                startupFailure.set(error);
            }
        }, "cubism-editor-startup");
        editorThread.setDaemon(true);
        editorThread.start();

        Object appController = waitForController(startupFailure);
        AtomicReference<Throwable> openFailure = new AtomicReference<>();
        SwingUtilities.invokeAndWait(() -> {
            try {
                Method open = appController.getClass().getMethod(
                        "command_open", File.class, boolean.class);
                open.invoke(appController, sourcePath.toFile(), false);
            } catch (InvocationTargetException error) {
                openFailure.set(error.getTargetException());
            } catch (Throwable error) {
                openFailure.set(error);
            }
        });
        if (openFailure.get() != null) {
            throw new RuntimeException("Cubism explicit document open failed", openFailure.get());
        }
        Object modelSource = waitForModelSource(appController, startupFailure);
        System.out.println("EXPORT-RUNNER: model loaded: " + sourcePath.getFileName());

        AtomicReference<List<?>> files = new AtomicReference<>();
        AtomicReference<Throwable> exportFailure = new AtomicReference<>();
        SwingUtilities.invokeAndWait(() -> {
            try {
                files.set(exportModel(modelSource));
            } catch (InvocationTargetException error) {
                exportFailure.set(error.getTargetException());
            } catch (Throwable error) {
                exportFailure.set(error);
            }
        });
        if (exportFailure.get() != null) {
            throw new RuntimeException("Cubism runtime export failed", exportFailure.get());
        }
        if (files.get() == null || files.get().isEmpty()) {
            throw new IllegalStateException("Cubism exporter returned no files");
        }

        writePairs(files.get(), outputDirectory);
        System.out.println("EXPORT-RUNNER: complete: " + files.get().size() + " files");
        System.out.flush();
        System.err.flush();
        System.exit(0);
    }

    private static Object waitForController(AtomicReference<Throwable> startupFailure)
            throws Exception {
        Class<?> appClass = Class.forName("com.live2d.cubism.CECubismEditorApp");
        Field singletonField = appClass.getField("a");
        Object singleton = singletonField.get(null);
        Method appControllerMethod = appClass.getMethod("a");

        long deadline = System.currentTimeMillis() + LOAD_TIMEOUT_MS;
        while (System.currentTimeMillis() < deadline) {
            if (startupFailure.get() != null) {
                throw new RuntimeException("Cubism Editor startup failed", startupFailure.get());
            }
            Object controller = appControllerMethod.invoke(singleton);
            if (controller != null) {
                Object completePack = invokeNoArg(controller, "getCompletePack");
                if (completePack != null) {
                    return controller;
                }
            }
            Thread.sleep(200L);
        }
        throw new IllegalStateException("Timed out waiting for Cubism controller setup");
    }

    private static Object waitForModelSource(
            Object controller,
            AtomicReference<Throwable> startupFailure) throws Exception {
        long deadline = System.currentTimeMillis() + LOAD_TIMEOUT_MS;
        Object lastSource = null;
        long sourceSeenAt = 0L;
        while (System.currentTimeMillis() < deadline) {
            if (startupFailure.get() != null) {
                throw new RuntimeException("Cubism Editor startup failed", startupFailure.get());
            }
            Object completePack = invokeNoArg(controller, "getCompletePack");
            if (completePack != null) {
                Object document = invokeNoArg(completePack, "getCurrentDoc");
                if (document != null) {
                    Method getModelSource = findNoArgMethod(document.getClass(), "getModelSource");
                    if (getModelSource != null) {
                        Object source = getModelSource.invoke(document);
                        if (source != null) {
                            if (source != lastSource) {
                                lastSource = source;
                                sourceSeenAt = System.currentTimeMillis();
                            }
                            // The document becomes current just before final loader work settles.
                            if (System.currentTimeMillis() - sourceSeenAt >= 2_000L) {
                                return source;
                            }
                        }
                    }
                }
            }
            Thread.sleep(200L);
        }
        throw new IllegalStateException("Timed out waiting for Cubism to load the CMO3");
    }

    private static List<?> exportModel(Object source) throws Exception {
        ClassLoader loader = source.getClass().getClassLoader();
        Object textureManager = invokeNoArg(source, "getTextureManager");
        List<?> atlases = (List<?>) invokeNoArg(textureManager, "getTextureAtlases");
        int atlasEntries = 0;
        for (Object atlas : atlases) {
            atlasEntries += ((List<?>) invokeNoArg(atlas, "getModelImages")).size();
        }
        System.out.println("EXPORT-RUNNER: loaded atlases=" + atlases.size()
                + ", atlas model-image entries=" + atlasEntries);
        invokeNoArg(textureManager, "changeModelTextureInput_toAtlas");

        Class<?> exporterClass = Class.forName(
                "com.live2d.cubism.doc.model.exporter.b", true, loader);
        Object exporter = exporterClass.getConstructor().newInstance();
        Object setting = exporterClass.getMethod("a").invoke(exporter);
        invokeOneArg(setting, "setup", source);
        invokeOneArg(setting, "setEnableExtendEdgeColor", true);

        Object canvas = invokeNoArg(source, "getCanvas");
        int canvasWidth = ((Number) invokeNoArg(canvas, "getPixelWidth")).intValue();
        int canvasHeight = ((Number) invokeNoArg(canvas, "getPixelHeight")).intValue();
        float pixelsPerUnit = (float) Math.min(canvasWidth, canvasHeight);
        invokeOneArg(setting, "setCanvasWidth", canvasWidth);
        invokeOneArg(setting, "setCanvasHeight", canvasHeight);
        invokeOneArg(setting, "setPixelsPerUnit", pixelsPerUnit);
        invokeOneArg(setting, "setExportDisplayInfoJson", true);

        Method mocBridge = null;
        for (Method candidate : exporterClass.getDeclaredMethods()) {
            Class<?>[] parameters = candidate.getParameterTypes();
            if (Modifier.isStatic(candidate.getModifiers())
                    && candidate.getName().equals("a")
                    && parameters.length == 3
                    && parameters[0] == exporterClass
                    && parameters[1].isInstance(source)) {
                mocBridge = candidate;
                break;
            }
        }
        if (mocBridge == null) {
            throw new NoSuchMethodException("Cubism moc export bridge");
        }
        mocBridge.setAccessible(true);
        Object exportResult = mocBridge.invoke(null, exporter, source, null);
        if (exportResult == null) {
            throw new IllegalStateException("Cubism moc exporter returned null");
        }
        Object exportedTextures = invokeNoArg(exportResult, "b");
        System.out.println("EXPORT-RUNNER: moc texture images="
                + ((List<?>) exportedTextures).size());

        Object version = invokeNoArg(setting, "getVersion");
        Object jsonFormat = invokeNoArg(version, "b");
        Class<?> companionClass = Class.forName(
                "com.live2d.cubism.doc.model.exporter.b$a", true, loader);
        Field companionField = exporterClass.getField("a");
        Object companion = companionField.get(null);
        Class<?> exportTargetClass = Class.forName(
                "com.live2d.cubism.doc.model.exporter.b$b", true, loader);
        @SuppressWarnings({"rawtypes", "unchecked"})
        Object sdk = Enum.valueOf((Class<? extends Enum>) exportTargetClass.asSubclass(Enum.class), "SDK");

        Method packageBridge = null;
        for (Method candidate : companionClass.getDeclaredMethods()) {
            Class<?>[] parameters = candidate.getParameterTypes();
            if (Modifier.isStatic(candidate.getModifiers())
                    && candidate.getName().equals("a")
                    && parameters.length == 14
                    && parameters[0] == companionClass
                    && parameters[1] == String.class
                    && parameters[13] == exportTargetClass) {
                packageBridge = candidate;
                break;
            }
        }
        if (packageBridge == null) {
            throw new NoSuchMethodException("Cubism package export bridge");
        }
        packageBridge.setAccessible(true);
        Object packaged = packageBridge.invoke(
                null,
                companion,
                "Jade",
                source,
                exportResult,
                jsonFormat,
                1,
                false,
                false,
                false,
                false,
                true,
                false,
                true,
                sdk);
        if (!(packaged instanceof List<?>)) {
            throw new IllegalStateException("Cubism package exporter returned "
                    + (packaged == null ? "null" : packaged.getClass().getName()));
        }
        System.out.println("EXPORT-RUNNER: canvas=" + canvasWidth + "x" + canvasHeight
                + ", PPU=" + pixelsPerUnit + ", format=" + jsonFormat);
        return (List<?>) packaged;
    }

    private static void writePairs(List<?> pairs, Path outputDirectory) throws Exception {
        for (Object pair : pairs) {
            Object nameObject = invokeNoArg(pair, "getFirst");
            Object bytesObject = invokeNoArg(pair, "getSecond");
            if (!(nameObject instanceof String) || !(bytesObject instanceof byte[])) {
                throw new IllegalStateException("Unexpected Cubism output pair: " + pair);
            }
            String name = ((String) nameObject).replace('\\', '/');
            Path destination = outputDirectory.resolve(name).normalize();
            if (!destination.startsWith(outputDirectory)) {
                throw new IllegalArgumentException("Unsafe Cubism output path: " + name);
            }
            Files.createDirectories(destination.getParent());
            byte[] bytes = (byte[]) bytesObject;
            Files.write(
                    destination,
                    bytes,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.TRUNCATE_EXISTING,
                    StandardOpenOption.WRITE);
            System.out.println("EXPORT-RUNNER: wrote " + name + " (" + bytes.length + " bytes)");
        }
    }

    private static Object invokeNoArg(Object target, String name) throws Exception {
        Method method = findNoArgMethod(target.getClass(), name);
        if (method == null) {
            throw new NoSuchMethodException(target.getClass().getName() + "." + name + "()");
        }
        method.setAccessible(true);
        return method.invoke(target);
    }

    private static Method findNoArgMethod(Class<?> type, String name) {
        for (Class<?> current = type; current != null; current = current.getSuperclass()) {
            for (Method method : current.getDeclaredMethods()) {
                if (method.getName().equals(name) && method.getParameterCount() == 0) {
                    return method;
                }
            }
        }
        return null;
    }

    private static Object invokeOneArg(Object target, String name, Object value) throws Exception {
        for (Method method : target.getClass().getMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == 1
                    && isCompatible(method.getParameterTypes()[0], value)) {
                return method.invoke(target, value);
            }
        }
        throw new NoSuchMethodException(target.getClass().getName() + "." + name + "(value)");
    }

    private static boolean isCompatible(Class<?> parameter, Object value) {
        if (value == null) {
            return !parameter.isPrimitive();
        }
        if (!parameter.isPrimitive()) {
            return parameter.isInstance(value);
        }
        return (parameter == boolean.class && value instanceof Boolean)
                || (parameter == int.class && value instanceof Integer)
                || (parameter == float.class && value instanceof Float)
                || (parameter == long.class && value instanceof Long)
                || (parameter == double.class && value instanceof Double);
    }
}
