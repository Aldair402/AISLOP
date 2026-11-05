//! Barrera para la futura inicialización de clase concurrente.
//! El backend generado aún usa su propia implementación monohilo.
use std::panic::{catch_unwind, resume_unwind, AssertUnwindSafe};
use std::sync::{Condvar, Mutex};
use std::thread::{self, ThreadId};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum InitError {
    FirstFailure,
    PreviouslyFailed,
}
#[derive(Default)]
enum State {
    #[default]
    Uninitialized,
    Initializing(ThreadId),
    Initialized,
    Failed,
}
#[derive(Default)]
pub struct ClassInit {
    state: Mutex<State>,
    changed: Condvar,
}

impl ClassInit {
    /// Corre init una sola vez; las llamadas reentrantes del propietario vuelven
    /// inmediatamente, otras esperan. Todavía no traduce causas Java.
    pub fn ensure(&self, init: impl FnOnce() -> Result<(), ()>) -> Result<(), InitError> {
        let owner = thread::current().id();
        let mut state = self.state.lock().expect("estado de inicialización dañado");
        loop {
            match *state {
                State::Initialized => return Ok(()),
                State::Failed => return Err(InitError::PreviouslyFailed),
                State::Initializing(id) if id == owner => return Ok(()),
                State::Initializing(_) => {
                    state = self
                        .changed
                        .wait(state)
                        .expect("estado de inicialización dañado")
                }
                State::Uninitialized => {
                    *state = State::Initializing(owner);
                    break;
                }
            }
        }
        drop(state);
        let result = catch_unwind(AssertUnwindSafe(init));
        let mut state = self.state.lock().expect("estado de inicialización dañado");
        *state = if matches!(result, Ok(Ok(()))) {
            State::Initialized
        } else {
            State::Failed
        };
        self.changed.notify_all();
        drop(state);
        match result {
            Ok(Ok(())) => Ok(()),
            Ok(Err(())) => Err(InitError::FirstFailure),
            Err(p) => resume_unwind(p),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scheduler::WorkerPool;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::{Arc, Barrier};

    #[test]
    fn one_initializer_and_reentrant_owner() {
        let gate = Arc::new(Barrier::new(9));
        let init = Arc::new(ClassInit::default());
        let calls = Arc::new(AtomicUsize::new(0));
        let pool = WorkerPool::new(8).unwrap();
        for _ in 0..8 {
            let (g, s, c) = (gate.clone(), init.clone(), calls.clone());
            pool.execute(move || {
                g.wait();
                s.ensure(|| {
                    c.fetch_add(1, Ordering::SeqCst);
                    s.ensure(|| panic!("reentrada no debe reiniciar")).unwrap();
                    Ok(())
                })
                .unwrap();
            })
            .unwrap();
        }
        gate.wait();
        assert_eq!(pool.shutdown(), Ok(0));
        assert_eq!(calls.load(Ordering::SeqCst), 1);
    }
    #[test]
    fn failure_is_sticky_and_wakes_waiters() {
        let init = Arc::new(ClassInit::default());
        let gate = Arc::new(Barrier::new(5));
        let first = Arc::new(AtomicUsize::new(0));
        let later = Arc::new(AtomicUsize::new(0));
        let pool = WorkerPool::new(4).unwrap();
        for _ in 0..4 {
            let (i, g, f, l) = (init.clone(), gate.clone(), first.clone(), later.clone());
            pool.execute(move || {
                g.wait();
                match i.ensure(|| Err(())) {
                    Err(InitError::FirstFailure) => {
                        f.fetch_add(1, Ordering::SeqCst);
                    }
                    Err(InitError::PreviouslyFailed) => {
                        l.fetch_add(1, Ordering::SeqCst);
                    }
                    _ => panic!("fallo omitido"),
                }
            })
            .unwrap();
        }
        gate.wait();
        assert_eq!(pool.shutdown(), Ok(0));
        assert_eq!(first.load(Ordering::SeqCst), 1);
        assert_eq!(later.load(Ordering::SeqCst), 3);
    }
    #[test]
    fn rust_panic_does_not_leave_class_initializing() {
        let c = ClassInit::default();
        let p = std::panic::catch_unwind(|| {
            let _ = c.ensure(|| panic!("fallo"));
        });
        assert!(p.is_err());
        assert_eq!(c.ensure(|| Ok(())), Err(InitError::PreviouslyFailed));
    }
}
