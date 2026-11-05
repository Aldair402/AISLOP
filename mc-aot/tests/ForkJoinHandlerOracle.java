import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.ForkJoinTask;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Semántica observable Java: no implementa ni prueba el adaptador Rust. */
public class ForkJoinHandlerOracle {
    static void check(boolean v, String label) { if (!v) throw new AssertionError(label); }
    public static void main(String[] args) throws Exception {
        var calls = new AtomicInteger();
        var signal = new CountDownLatch(1);
        var observed = new AtomicReference<Throwable>();
        var worker = new AtomicReference<Thread>();
        var marker = new IllegalStateException("execute");
        ForkJoinPool p = new ForkJoinPool(1, ForkJoinPool.defaultForkJoinWorkerThreadFactory,
            (t, e) -> { observed.set(e); worker.set(t); calls.incrementAndGet(); signal.countDown(); }, true);
        p.execute(() -> { throw marker; });
        check(signal.await(5, TimeUnit.SECONDS), "handler no invocado");
        check(observed.get() == marker && worker.get() != null, "identidad/worker handler");
        System.out.println("execute|handler|misma-excepcion");

        var submitFailure = new IllegalArgumentException("submit");
        ForkJoinTask<?> task = p.submit(() -> { throw submitFailure; });
        try { task.join(); throw new AssertionError("join no lanzo"); }
        catch (IllegalArgumentException expected) { }
        try { task.get(); throw new AssertionError("get no lanzo"); }
        catch (ExecutionException expected) { check(expected.getCause() instanceof IllegalArgumentException, "causa get"); }
        check(calls.get() == 1, "submit invoco handler");
        System.out.println("submit|join-excepcion|get-executionexception|sin-handler");

        var asyncFailure = new UnsupportedOperationException("async");
        var cf = CompletableFuture.supplyAsync(() -> {throw asyncFailure;}, p);
        try { cf.join(); throw new AssertionError("future join no lanzo"); }
        catch (CompletionException e) { check(e.getCause() == asyncFailure, "cause join future"); }
        try { cf.get(); throw new AssertionError("future get no lanzo"); }
        catch (ExecutionException e) { check(e.getCause() == asyncFailure, "cause get future"); }
        check(calls.get() == 1, "future invoco handler");
        System.out.println("supplyAsync|causa-identica|sin-handler");

        p.shutdown();
        check(p.awaitTermination(5, TimeUnit.SECONDS), "no termino");
        try { p.submit(() -> {}); throw new AssertionError("acepto tras shutdown"); }
        catch (RejectedExecutionException expected) { }
        check(calls.get() == 1, "handler extra");
        System.out.println("shutdown|terminacion|rechazo");
    }
}
