import java.util.concurrent.CancellationException;
import java.util.concurrent.CompletableFuture;

/**
 * Oráculo de cancelación de futuros pendientes (JDK 25), 40 rondas por bandera.
 *
 * Fija lo que Java hace y el adaptador todavía no: cancel(true) y cancel(false) son
 * indistinguibles en CompletableFuture, porque el flag mayInterruptIfRunning no
 * interrumpe a nadie (no hay hilo asociado al futuro).
 *
 * Salida esperada, comprobada por check-rayon-pending-future.py:
 *   cancel(false): cancelTrue=40/40 isDone=40/40 isCancelled=40/40
 *                  isCompletedExceptionally=40/40 getCancellation=40/40
 *                  joinCancellation=40/40 getNowCancellation=40/40 completeAfterFalse=40/40
 *   cancel(true):  los mismos ocho contadores
 *   cancel(true) sobre completado devuelve false=40/40
 */
public class CompletableFutureCancelOracle {
    interface R { void run(); }

    static boolean cancela(R r) {
        try {
            r.run();
            return false;
        } catch (CancellationException e) {
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    public static void main(String[] args) {
        for (boolean flag : new boolean[] {false, true}) {
            int cancelTrue = 0, done = 0, cancelled = 0, exc = 0;
            int getC = 0, joinC = 0, nowC = 0, completeAfter = 0;
            for (int i = 0; i < 40; i++) {
                CompletableFuture<Object> cf = new CompletableFuture<>();
                if (cf.cancel(flag)) cancelTrue++;
                if (cf.isDone()) done++;
                if (cf.isCancelled()) cancelled++;
                if (cf.isCompletedExceptionally()) exc++;
                final CompletableFuture<Object> f = cf;
                if (cancela(() -> {
                    try {
                        f.get();
                    } catch (CancellationException e) {
                        throw e;
                    } catch (Exception e) {
                        // otro tipo de fallo no cuenta como cancelación
                    }
                })) getC++;
                if (cancela(() -> f.join())) joinC++;
                if (cancela(() -> f.getNow("def"))) nowC++;
                if (!cf.complete("x")) completeAfter++;
            }
            System.out.println("cancel(" + flag + "): cancelTrue=" + cancelTrue +
                    "/40 isDone=" + done + "/40 isCancelled=" + cancelled +
                    "/40 isCompletedExceptionally=" + exc + "/40 getCancellation=" + getC +
                    "/40 joinCancellation=" + joinC + "/40 getNowCancellation=" + nowC +
                    "/40 completeAfterFalse=" + completeAfter + "/40");
        }
        int sobreCompletado = 0;
        for (int i = 0; i < 40; i++) {
            if (!CompletableFuture.completedFuture("v").cancel(true)) sobreCompletado++;
        }
        System.out.println("cancel(true) sobre completado devuelve false=" + sobreCompletado + "/40");
    }
}
