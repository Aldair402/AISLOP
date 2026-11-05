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

        // submit(Callable): el valor viaja, pero el adaptador NO conserva la
        // identidad de la causa: get() devuelve una ExecutionException cuyo
        // cause es un envoltorio nuevo. El handler tampoco se invoca.
        ForkJoinTask<Integer> callableValue = p.submit(() -> 7);
        check(callableValue.get() == 7, "submit(Callable) valor");
        var callableFailure = new IllegalStateException("callable");
        ForkJoinTask<Integer> failedCallable = p.submit(() -> { throw callableFailure; });
        try { failedCallable.get(); throw new AssertionError("submit(Callable) get no lanzo"); }
        catch (ExecutionException e) {
            check(e.getCause() != null, "cause no nula");
            check(e.getCause() != callableFailure, "Callable no conserva la identidad de la causa");
        }
        check(calls.get() == 1, "submit(Callable) invoco el handler");
        System.out.println("submitCallable|valor|causa-envuelta|sin-handler");

        // invoke(): relanza la excepcion original o una cuyo cause es la original;
        // nunca la pierde. El handler no participa.
        var invokeFailure = new IllegalArgumentException("invoke");
        try { p.submit(() -> { throw invokeFailure; }).invoke(); throw new AssertionError("invoke no lanzo"); }
        catch (Throwable e) { check(e == invokeFailure || e.getCause() == invokeFailure, "invoke perdio la causa"); }
        check(calls.get() == 1, "invoke invoco el handler");
        System.out.println("invoke|original-o-causa|sin-handler");

        // commonPool(): instancia estable y paralelismo utilizable.
        check(ForkJoinPool.commonPool() == ForkJoinPool.commonPool(), "commonPool identidad");
        check(ForkJoinPool.commonPool().getParallelism() >= 1, "commonPool paralelismo");
        System.out.println("commonPool|misma-instancia|paralelismo-positivo");

        // Contadores de workers: no se promete creacion gradual ni valores exactos,
        // solo que no exceden el paralelismo y que hay al menos uno tras usarlo.
        var counters = new ForkJoinPool(2);
        check(counters.getPoolSize() <= counters.getParallelism(), "workers fuera del paralelismo");
        check(counters.getActiveThreadCount() >= 0, "active negativo");
        check(counters.getRunningThreadCount() >= 0, "running negativo");
        check(counters.getQueuedSubmissionCount() >= 0, "queued negativo");
        check(counters.getQueuedTaskCount() >= 0, "queuedTask negativo");
        counters.submit(() -> {}).join();
        check(counters.getPoolSize() >= 1, "sin worker tras uso");
        check(counters.getPoolSize() <= counters.getParallelism(), "workers fuera del paralelismo tras uso");
        counters.shutdown();
        check(counters.awaitTermination(5, TimeUnit.SECONDS), "counters no termino");
        check(counters.isTerminated(), "counters no quedo terminado");
        System.out.println("workerCounters|dentro-del-paralelismo|uno-o-mas-tras-uso|cierre");

        p.shutdown();
        check(p.awaitTermination(5, TimeUnit.SECONDS), "no termino");
        try { p.submit(() -> {}); throw new AssertionError("acepto tras shutdown"); }
        catch (RejectedExecutionException expected) { }
        check(calls.get() == 1, "handler extra");
        System.out.println("shutdown|terminacion|rechazo");
    }
}
