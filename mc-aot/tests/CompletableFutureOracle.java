import java.util.concurrent.CancellationException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Oráculo Java 25: semántica observada, no implementación nativa. */
public class CompletableFutureOracle {
    private static void expect(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        Object marker = new Object();
        var nil = CompletableFuture.completedFuture(null);
        expect(nil.join() == null && nil.getNow(marker) == null && nil.isDone(), "completed null");
        var one = new CompletableFuture<Object>();
        expect(one.getNow(marker) == marker && !one.isDone(), "pending default identity");
        expect(one.complete(marker) && !one.complete(new Object()) && one.join() == marker, "complete once");
        System.out.println("normal|null|identity|complete-once");

        var cause = new IllegalStateException("boom");
        var fail = new CompletableFuture<Object>();
        expect(fail.completeExceptionally(cause) && !fail.complete(marker), "exceptional complete");
        try { fail.join(); throw new AssertionError("join"); }
        catch (CompletionException e) { expect(e.getCause() == cause, "join cause"); }
        try { fail.get(); throw new AssertionError("get"); }
        catch (ExecutionException e) { expect(e.getCause() == cause, "get cause"); }
        System.out.println("exception|join-completion|get-execution|same-cause");

        var cancelled = new CompletableFuture<Object>();
        expect(cancelled.cancel(false) && cancelled.isCancelled() && cancelled.isCompletedExceptionally(), "cancelled");
        try { cancelled.join(); throw new AssertionError("cancel join"); }
        catch (CancellationException expected) { }
        try { cancelled.get(); throw new AssertionError("cancel get"); }
        catch (CancellationException expected) { }
        System.out.println("cancel|join-direct|get-direct");

        var a = new CompletableFuture<Object>();
        var b = new CompletableFuture<Object>();
        var all = CompletableFuture.allOf(a, b);
        a.completeExceptionally(cause);
        expect(!all.isDone(), "allOf waits for second");
        b.complete(marker);
        try { all.join(); throw new AssertionError("allOf"); }
        catch (CompletionException e) { expect(e.getCause() == cause, "allOf cause"); }
        expect(CompletableFuture.allOf().join() == null, "allOf empty");
        System.out.println("allOf|wait-all|same-cause|empty-null");

        var source = new CompletableFuture<String>();
        var chained = source.thenApply(v -> Thread.currentThread().getName() + ":" + v);
        Thread completing = new Thread(() -> source.complete("ok"), "future-completer");
        completing.start(); completing.join();
        expect(chained.join().equals("future-completer:ok"), "non-async callback thread");
        var calls = new AtomicInteger();
        var direct = new CompletableFuture<String>();
        var async = direct.thenApplyAsync(v -> v + "!", task -> { calls.incrementAndGet(); task.run(); });
        direct.complete("ok");
        expect(async.join().equals("ok!") && calls.get() == 1, "executor used");
        var rejected = CompletableFuture.completedFuture("x").thenApplyAsync(v -> v, task -> {throw new RejectedExecutionException("reject");});
        try { rejected.join(); throw new AssertionError("rejection"); }
        catch (CompletionException e) { expect(e.getCause() instanceof RejectedExecutionException, "rejected cause"); }
        System.out.println("callbacks|completer-thread|explicit-executor|rejection-cause");

        var timed = new CompletableFuture<Object>();
        try { timed.get(0, TimeUnit.NANOSECONDS); throw new AssertionError("timeout"); }
        catch (TimeoutException expected) { expect(!timed.isDone(), "timeout not completion"); }
        System.out.println("timeout|pending");

        var interrupted = new CompletableFuture<Object>();
        var ready = new CountDownLatch(1);
        var interruptedResult = new AtomicReference<String>();
        Thread getter = new Thread(() -> {
            ready.countDown();
            try { interrupted.get(); interruptedResult.set("returned"); }
            catch (InterruptedException e) { interruptedResult.set("interrupted:" + Thread.currentThread().isInterrupted()); }
            catch (ExecutionException e) { interruptedResult.set("execution"); }
        }, "future-getter");
        getter.start(); ready.await(); getter.interrupt(); getter.join(5000);
        expect(!getter.isAlive() && "interrupted:false".equals(interruptedResult.get()) && !interrupted.isDone(), "get interruption");
        interrupted.complete(marker);

        var joining = new CompletableFuture<Object>();
        var joinReady = new CountDownLatch(1);
        var joinResult = new AtomicReference<String>();
        Thread joiner = new Thread(() -> {
            Thread.currentThread().interrupt(); joinReady.countDown();
            Object v = joining.join();
            joinResult.set((v == marker) + ":" + Thread.currentThread().isInterrupted());
        }, "future-joiner");
        joiner.start(); joinReady.await(); joining.complete(marker); joiner.join(5000);
        expect(!joiner.isAlive() && "true:true".equals(joinResult.get()), "join interruption");
        System.out.println("interrupt|get-throws-cleared|join-returns-preserved");
    }
}
