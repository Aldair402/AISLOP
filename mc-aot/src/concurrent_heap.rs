//! Prototipo de heap compartido y monitores para el backend futuro.
//! Conectado al backend concurrente experimental; no implementa GC ni el modelo completo JVM.
use std::marker::PhantomData;
use std::rc::Rc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread::{self, ThreadId};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ObjectId {
    heap: u64,
    index: usize,
}
static NEXT_HEAP: AtomicU64 = AtomicU64::new(1);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Value {
    Int(i32),
    Long(i64),
    Ref(Option<ObjectId>),
    Void,
}

/// Puente experimental interno: el adaptador confiable provee almacenamiento
/// y monitor. SharedHeap valida que las referencias devueltas sean de este heap;
/// no supone semántica general de tipos, clases, excepciones ni memoria JVM.
pub trait ExternalGuard {}
impl<T> ExternalGuard for T {}
#[derive(Clone,Copy)] pub enum ExternalValue { Int(i32), Ref(Option<ObjectId>) }
pub trait ExternalObject: Send + Sync {
    fn identity_key(&self) -> usize;
    fn domain_key(&self) -> usize;
    fn class(&self) -> &'static str;
    fn field_count(&self) -> Result<usize, &'static str>;
    fn read(&self, field:usize) -> Result<ExternalValue, &'static str>;
    fn write(&self, field:usize, value:ExternalValue) -> Result<(), &'static str>;
    fn enter(&self) -> Result<Box<dyn ExternalGuard>, &'static str>;
}
struct Object {
    external: Option<Arc<dyn ExternalObject>>,
    external_domain: Option<usize>,
    class: Option<&'static str>,
    fields: Vec<Value>,
    monitor: Arc<Monitor>,
    string_units: Option<Vec<u16>>,
    worker_name: Option<ObjectId>,
}
struct Store {
    id: u64,
    objects: Vec<Object>,
    fields: usize,
    default_forkjoin_factory: Option<ObjectId>,
    time_units: [Option<ObjectId>; 7],
    interned_strings: std::collections::HashMap<Vec<u16>, ObjectId>,
    external_ids: std::collections::HashMap<usize,ObjectId>,
    string_units_count: usize,
}
impl Default for Store {
    fn default() -> Self {
        #[allow(deprecated)] // fetch_update también existe en toolchains Rust anteriores.
        let id = NEXT_HEAP
            .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |n| n.checked_add(1))
            .unwrap_or_else(|_| panic!("identificadores de heap agotados"));
        Self {
            id,
            objects: Vec::new(),
            fields: 0,
            default_forkjoin_factory: None,
            time_units: [None; 7],
            interned_strings: std::collections::HashMap::new(),
            external_ids: std::collections::HashMap::new(),
            string_units_count: 0,
        }
    }
}
impl Store {
    fn check(&self, id: ObjectId) -> Result<usize, &'static str> {
        if id.heap != self.id || id.index >= self.objects.len() {
            return Err("objeto inválido");
        }
        Ok(id.index)
    }
    fn check_value(&self, value: Value) -> Result<(), &'static str> {
        if let Value::Ref(Some(id)) = value {
            self.check(id)?;
        }
        Ok(())
    }
}
#[derive(Clone, Default)]
pub struct SharedHeap {
    store: Arc<Mutex<Store>>,
}

impl SharedHeap {
    /// La identidad del adaptador debe ser estable mientras el heap lo retenga.
    /// El registro es local a este heap; fuera de él se rechaza el ObjectId.
    pub fn attach_external(&self, object:Arc<dyn ExternalObject>) -> Result<ObjectId, &'static str> {
        let key=object.identity_key();let domain=object.domain_key();let class=object.class();let count=object.field_count()?;
        if !class.starts_with("net/minecraft/") {return Err("objeto externo fuera del perfil");}
        let mut store=self.store.lock().map_err(|_|"heap dañado")?;
        if let Some(id)=store.external_ids.get(&key).copied() {
            let index=store.check(id)?;if store.objects[index].class!=Some(class) || store.objects[index].external_domain!=Some(domain) {return Err("identidad externa incompatible");}
            return Ok(id);
        }
        if store.objects.len()>=10_000 || store.fields.checked_add(count).map_or(true,|v|v>1_000_000) {return Err("límite de objetos o campos");}
        let id=ObjectId{heap:store.id,index:store.objects.len()};store.fields+=count;
        store.objects.push(Object{external:Some(object),external_domain:Some(domain),class:Some(class),fields:vec![],monitor:Arc::new(Monitor::default()),string_units:None,worker_name:None});
        store.external_ids.insert(key,id);Ok(id)
    }
    pub fn allocate(&self, fields: Vec<Value>) -> Result<ObjectId, &'static str> {
        self.allocate_internal(None, fields)
    }
    pub fn allocate_typed(
        &self,
        class: &'static str,
        fields: Vec<Value>,
    ) -> Result<ObjectId, &'static str> {
        self.allocate_internal(Some(class), fields)
    }
    fn allocate_internal(
        &self,
        class: Option<&'static str>,
        fields: Vec<Value>,
    ) -> Result<ObjectId, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        if store.objects.len() >= 10_000 {
            return Err("límite de objetos");
        }
        if store
            .fields
            .checked_add(fields.len())
            .map_or(true, |n| n > 1_000_000)
        {
            return Err("límite de campos");
        }
        for &v in &fields {
            store.check_value(v)?;
        }
        let id = ObjectId {
            heap: store.id,
            index: store.objects.len(),
        };
        store.fields += fields.len();
        store.objects.push(Object {
            external: None,
            external_domain: None,
            class,
            fields,
            monitor: Arc::new(Monitor::default()),
            string_units: None,
            worker_name: None,
        });
        Ok(id)
    }
    /// Literales Java internados por unidades UTF-16, incluso sustitutos aislados.
    pub fn intern_string(&self, units: &[u16]) -> Result<ObjectId, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        if let Some(id) = store.interned_strings.get(units) {
            return Ok(*id);
        }
        if store.objects.len() >= 10_000
            || store
                .string_units_count
                .checked_add(units.len())
                .map_or(true, |n| n > 1_000_000)
        {
            return Err("límite de literales String");
        }
        let id = ObjectId {
            heap: store.id,
            index: store.objects.len(),
        };
        store.string_units_count += units.len();
        store.objects.push(Object {
            external: None,
            external_domain: None,
            class: Some("java/lang/String"),
            fields: vec![],
            monitor: Arc::new(Monitor::default()),
            string_units: Some(units.to_vec()),
            worker_name: None,
        });
        store.interned_strings.insert(units.to_vec(), id);
        Ok(id)
    }
    /// Subconjunto StringConcatFactory: receta con String e int, resultado nuevo.
    pub fn concat_string_int(
        &self,
        text: Option<ObjectId>,
        number: i32,
        recipe: &[u16],
    ) -> Result<ObjectId, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        let value = if let Some(id) = text {
            let idx = store.check(id)?;
            store.objects[idx]
                .string_units
                .clone()
                .ok_or("String inesperado")?
        } else {
            "null".encode_utf16().collect()
        };
        let digits = number.to_string().encode_utf16().collect::<Vec<_>>();
        let mut result = Vec::new();
        let mut arg = 0;
        for &c in recipe {
            match c {
                1 => {
                    match arg {
                        0 => result.extend_from_slice(&value),
                        1 => result.extend_from_slice(&digits),
                        _ => return Err("receta concat inválida"),
                    };
                    arg += 1;
                }
                2 => return Err("constante concat no soportada"),
                _ => result.push(c),
            }
            if result.len() > 1_000_000 {
                return Err("límite de String");
            }
        }
        if arg != 2 {
            return Err("receta concat inválida");
        }
        if store.objects.len() >= 10_000
            || store
                .string_units_count
                .checked_add(result.len())
                .map_or(true, |n| n > 1_000_000)
        {
            return Err("límite de String");
        }
        let id = ObjectId {
            heap: store.id,
            index: store.objects.len(),
        };
        store.string_units_count += result.len();
        store.objects.push(Object {
            external: None,
            external_domain: None,
            class: Some("java/lang/String"),
            fields: vec![],
            monitor: Arc::new(Monitor::default()),
            string_units: Some(result),
            worker_name: None,
        });
        Ok(id)
    }
    /// Solo nombres explícitos de workers del perfil; no modela Thread general.
    pub fn set_worker_name(&self, worker: ObjectId, name: ObjectId) -> Result<(), &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        let w = store.check(worker)?;
        let n = store.check(name)?;
        let units = store.objects[n]
            .string_units
            .as_deref()
            .ok_or("nombre no String")?;
        if units.contains(&0) || String::from_utf16(units).is_err() {
            return Err("nombre worker no representable en Rust");
        }
        store.objects[w].worker_name = Some(name);
        Ok(())
    }
    pub fn worker_name(&self, worker: ObjectId) -> Result<Option<ObjectId>, &'static str> {
        let store = self.store.lock().map_err(|_| "heap dañado")?;
        let w = store.check(worker)?;
        Ok(store.objects[w].worker_name)
    }
    pub fn worker_os_name(&self, worker: ObjectId) -> Result<Option<String>, &'static str> {
        let store = self.store.lock().map_err(|_| "heap dañado")?;
        let w = store.check(worker)?;
        let Some(id) = store.objects[w].worker_name else {
            return Ok(None);
        };
        let n = store.check(id)?;
        let units = store.objects[n]
            .string_units
            .as_deref()
            .ok_or("nombre no String")?;
        let name =
            String::from_utf16(units).map_err(|_| "nombre worker no representable en Rust")?;
        if name.contains('\0') {
            return Err("nombre worker no representable en Rust");
        }
        Ok(Some(name))
    }
    pub fn string_hash(&self, id: ObjectId) -> Result<i32, &'static str> {
        let store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        let units = store.objects[index]
            .string_units
            .as_deref()
            .ok_or("String inesperado")?;
        Ok(units
            .iter()
            .fold(0_i32, |h, &c| h.wrapping_mul(31).wrapping_add(c as i32)))
    }
    pub fn string_length(&self, id: ObjectId) -> Result<i32, &'static str> {
        let store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        let units = store.objects[index]
            .string_units
            .as_deref()
            .ok_or("String inesperado")?;
        i32::try_from(units.len()).map_err(|_| "String demasiado largo")
    }
    /// Identidad única del marcador interno del factory predeterminado.
    pub fn default_forkjoin_factory(&self) -> Result<ObjectId, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        if let Some(id) = store.default_forkjoin_factory {
            return Ok(id);
        }
        if store.objects.len() >= 10_000 {
            return Err("límite de objetos");
        }
        let id = ObjectId {
            heap: store.id,
            index: store.objects.len(),
        };
        store.objects.push(Object {
            external: None,
            external_domain: None,
            class: Some("mc-aot/default-forkjoin-factory"),
            fields: vec![],
            monitor: Arc::new(Monitor::default()),
            string_units: None,
            worker_name: None,
        });
        store.default_forkjoin_factory = Some(id);
        Ok(id)
    }
    /// Conversión limitada de TimeUnit a nanosegundos para una espera.
    /// Un timeout no positivo equivale a no esperar y la conversión positiva
    /// se satura igual que TimeUnit.toNanos(long).
    pub fn timeout_nanos(&self, unit: ObjectId, timeout: i64) -> Result<u64, &'static str> {
        let factor: i128 = match self.class_of(unit)? {
            Some("mc-aot/TimeUnit/NANOSECONDS") => 1,
            Some("mc-aot/TimeUnit/MICROSECONDS") => 1_000,
            Some("mc-aot/TimeUnit/MILLISECONDS") => 1_000_000,
            Some("mc-aot/TimeUnit/SECONDS") => 1_000_000_000,
            Some("mc-aot/TimeUnit/MINUTES") => 60_000_000_000,
            Some("mc-aot/TimeUnit/HOURS") => 3_600_000_000_000,
            Some("mc-aot/TimeUnit/DAYS") => 86_400_000_000_000,
            _ => return Err("TimeUnit inesperado"),
        };
        Ok(if timeout <= 0 {
            0
        } else {
            ((timeout as i128) * factor).min(i64::MAX as i128) as u64
        })
    }
    pub fn time_unit(&self, index: usize) -> Result<ObjectId, &'static str> {
        const TYPES: [&str; 7] = [
            "mc-aot/TimeUnit/NANOSECONDS",
            "mc-aot/TimeUnit/MICROSECONDS",
            "mc-aot/TimeUnit/MILLISECONDS",
            "mc-aot/TimeUnit/SECONDS",
            "mc-aot/TimeUnit/MINUTES",
            "mc-aot/TimeUnit/HOURS",
            "mc-aot/TimeUnit/DAYS",
        ];
        let class = *TYPES.get(index).ok_or("TimeUnit no soportado")?;
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        if let Some(id) = store.time_units[index] {
            return Ok(id);
        }
        if store.objects.len() >= 10_000 {
            return Err("límite de objetos");
        }
        let id = ObjectId {
            heap: store.id,
            index: store.objects.len(),
        };
        store.objects.push(Object {
            external: None,
            external_domain: None,
            class: Some(class),
            fields: vec![],
            monitor: Arc::new(Monitor::default()),
            string_units: None,
            worker_name: None,
        });
        store.time_units[index] = Some(id);
        Ok(id)
    }
    pub fn class_of(&self, id: ObjectId) -> Result<Option<&'static str>, &'static str> {
        let store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        Ok(store.objects[index].class)
    }
    /// Operación RMW sobre el mismo lock que protege las lecturas/escrituras
    /// compartidas del heap; el retorno y el desbordamiento siguen a Java.
    pub fn atomic_get_and_increment(&self, id: ObjectId) -> Result<i32, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        let object = &mut store.objects[index];
        if object.class != Some("java/util/concurrent/atomic/AtomicInteger") {
            return Err("AtomicInteger inesperado");
        }
        let Some(Value::Int(old)) = object.fields.first_mut() else {
            return Err("AtomicInteger dañado");
        };
        let result = *old;
        *old = old.wrapping_add(1);
        Ok(result)
    }
    pub fn read(&self, id: ObjectId, field: usize) -> Result<Value, &'static str> {
        let store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        if let Some(external)=store.objects[index].external.clone() {
            drop(store);
            let value=match external.read(field)? {ExternalValue::Int(v)=>Value::Int(v),ExternalValue::Ref(id)=>Value::Ref(id)};
            let store=self.store.lock().map_err(|_|"heap dañado")?;store.check_value(value)?;return Ok(value);
        }
        store.objects[index].fields.get(field).copied().ok_or("objeto o campo inválido")
    }
    pub fn write(&self, id: ObjectId, field: usize, value: Value) -> Result<(), &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        store.check_value(value)?;
        if let Some(external)=store.objects[index].external.clone() {let value=match value {Value::Int(v)=>ExternalValue::Int(v),Value::Ref(v)=>ExternalValue::Ref(v),_=>return Err("puente: tipo no soportado")};drop(store);return external.write(field,value);}
        let slot = store.objects[index].fields.get_mut(field).ok_or("objeto o campo inválido")?;
        if std::mem::discriminant(slot) != std::mem::discriminant(&value) {return Err("tipo de campo incompatible");}
        *slot = value;Ok(())
    }
    /// Operación atómica experimental bajo el mutex del heap; para referencias
    /// compara identidad, no equals(). No sustituye al modelo de memoria JVM.
    pub fn compare_exchange(
        &self,
        id: ObjectId,
        field: usize,
        expected: Value,
        update: Value,
    ) -> Result<bool, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        store.check_value(expected)?;
        store.check_value(update)?;
        if store.objects[index].external.is_some() {return Err("CAS externo no soportado");}
        let slot = store
            .objects
            .get_mut(index)
            .and_then(|o| o.fields.get_mut(field))
            .ok_or("objeto o campo inválido")?;
        if std::mem::discriminant(slot) != std::mem::discriminant(&expected)
            || std::mem::discriminant(slot) != std::mem::discriminant(&update)
        {
            return Err("tipo de campo incompatible");
        }
        if *slot == expected {
            *slot = update;
            Ok(true)
        } else {
            Ok(false)
        }
    }
    pub fn get_and_add_int(
        &self,
        id: ObjectId,
        field: usize,
        delta: i32,
    ) -> Result<i32, &'static str> {
        let mut store = self.store.lock().map_err(|_| "heap dañado")?;
        let index = store.check(id)?;
        if store.objects[index].external.is_some() {return Err("RMW externo no soportado");}
        match store
            .objects
            .get_mut(index)
            .and_then(|o| o.fields.get_mut(field))
        {
            Some(Value::Int(value)) => {
                let old = *value;
                *value = old.wrapping_add(delta);
                Ok(old)
            }
            Some(_) => Err("tipo de campo incompatible"),
            None => Err("objeto o campo inválido"),
        }
    }
    pub fn enter(&self, id: ObjectId) -> Result<MonitorGuard, &'static str> {
        let monitor = {
            let store = self.store.lock().map_err(|_| "heap dañado")?;
            let index = store.check(id)?;
            if let Some(external)=store.objects[index].external.clone() {drop(store);return Ok(MonitorGuard::External(external.enter()?));}
            Arc::clone(&store.objects[index].monitor)
        };
        let current = thread::current().id();
        {
            let mut state = monitor.state.lock().map_err(|_| "monitor dañado")?;
            while state.owner.is_some() && state.owner != Some(current) {
                state = monitor.changed.wait(state).map_err(|_| "monitor dañado")?;
            }
            state.depth = state
                .depth
                .checked_add(1)
                .ok_or("profundidad de monitor excedida")?;
            state.owner = Some(current);
        }
        Ok(MonitorGuard::Local(LocalMonitorGuard {
            monitor,
            owner: current,
            not_send: PhantomData,
        }))
    }
}

#[derive(Default)]
struct MonitorState {
    owner: Option<ThreadId>,
    depth: usize,
}
#[derive(Default)]
struct Monitor {
    state: Mutex<MonitorState>,
    changed: Condvar,
}

/// No se puede mover a otro hilo, porque solo el propietario puede salir.
pub enum MonitorGuard { Local(LocalMonitorGuard), External(Box<dyn ExternalGuard>) }
pub struct LocalMonitorGuard {
    monitor: Arc<Monitor>,
    owner: ThreadId,
    not_send: PhantomData<Rc<()>>,
}
impl Drop for LocalMonitorGuard {
    fn drop(&mut self) {
        let mut state = self.monitor.state.lock().expect("monitor dañado");
        assert_eq!(state.owner, Some(self.owner));
        assert!(state.depth > 0);
        state.depth -= 1;
        if state.depth == 0 {
            state.owner = None;
            self.monitor.changed.notify_one();
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn concat_string_int_returns_fresh_utf16_value_and_handles_null() {
        let heap = super::SharedHeap::default();
        let text = heap.intern_string(&[0xd800, 0, 0xd83d, 0xde80]).unwrap();
        let recipe = [87, 111, 114, 107, 101, 114, 45, 1, 45, 1];
        let id = heap
            .concat_string_int(Some(text), i32::MIN, &recipe)
            .unwrap();
        let mut expected = "Worker-".encode_utf16().collect::<Vec<_>>();
        expected.extend([0xd800, 0, 0xd83d, 0xde80]);
        expected.extend("-".encode_utf16());
        expected.extend(i32::MIN.to_string().encode_utf16());
        assert_eq!(heap.string_length(id).unwrap(), expected.len() as i32);
        assert_eq!(
            heap.string_hash(id).unwrap(),
            expected
                .iter()
                .fold(0_i32, |h, &c| h.wrapping_mul(31).wrapping_add(c as i32))
        );
        assert_ne!(id, heap.intern_string(&expected).unwrap());
        let null = heap.concat_string_int(None, 1, &[1, 1]).unwrap();
        assert_eq!(
            heap.string_hash(null).unwrap(),
            "null1"
                .encode_utf16()
                .fold(0_i32, |h, c| h.wrapping_mul(31).wrapping_add(c as i32))
        );
        assert!(heap.concat_string_int(Some(text), 1, &[1]).is_err());
        assert!(heap.concat_string_int(Some(text), 1, &[1, 2, 1]).is_err());
    }
    #[test]
    fn interned_utf16_strings_share_identity_and_preserve_unpaired_surrogates() {
        let heap = super::SharedHeap::default();
        let units = vec![0x41, 0, 0xd83d, 0xde80, 0xd800];
        let threads = (0..16)
            .map(|_| {
                let h = heap.clone();
                let u = units.clone();
                std::thread::spawn(move || h.intern_string(&u).unwrap())
            })
            .collect::<Vec<_>>();
        let ids = threads
            .into_iter()
            .map(|t| t.join().unwrap())
            .collect::<Vec<_>>();
        assert!(ids.iter().all(|&id| id == ids[0]));
        assert_eq!(heap.string_length(ids[0]).unwrap(), 5);
        assert_eq!(
            heap.string_hash(ids[0]).unwrap(),
            units
                .iter()
                .fold(0_i32, |h, &c| h.wrapping_mul(31).wrapping_add(c as i32))
        );
        assert_ne!(
            heap.intern_string(&[0xd800]).unwrap(),
            heap.intern_string(&[0xfffd]).unwrap()
        );
        let fake = heap.allocate_typed("java/lang/String", vec![]).unwrap();
        assert!(heap.string_hash(fake).is_err());
        assert!(heap.intern_string(&vec![0; 1_000_001]).is_err());
    }
    #[test]
    fn atomic_increment_returns_unique_values_under_contention_and_wraps() {
        let heap = super::SharedHeap::default();
        let start = i32::MAX - 2000;
        let id = heap
            .allocate_typed(
                "java/util/concurrent/atomic/AtomicInteger",
                vec![super::Value::Int(start)],
            )
            .unwrap();
        let threads = (0..8)
            .map(|_| {
                let h = heap.clone();
                std::thread::spawn(move || {
                    (0..500)
                        .map(|_| h.atomic_get_and_increment(id).unwrap())
                        .collect::<Vec<_>>()
                })
            })
            .collect::<Vec<_>>();
        let mut got = threads
            .into_iter()
            .flat_map(|t| t.join().unwrap())
            .collect::<Vec<_>>();
        let mut expected = (0..4000_i32)
            .map(|x| start.wrapping_add(x))
            .collect::<Vec<_>>();
        got.sort_unstable();
        expected.sort_unstable();
        assert_eq!(got, expected);
        assert_eq!(
            heap.read(id, 0).unwrap(),
            super::Value::Int(start.wrapping_add(4000))
        );
        let other = heap.allocate(vec![super::Value::Int(0)]).unwrap();
        assert!(heap.atomic_get_and_increment(other).is_err());
    }
    #[test]
    fn time_unit_wait_conversion_is_saturating_and_interned() {
        let heap = super::SharedHeap::default();
        let factors = [
            1_u64,
            1_000,
            1_000_000,
            1_000_000_000,
            60_000_000_000,
            3_600_000_000_000,
            86_400_000_000_000,
        ];
        for (i, factor) in factors.into_iter().enumerate() {
            let unit = heap.time_unit(i).unwrap();
            assert_eq!(unit, heap.time_unit(i).unwrap());
            assert_eq!(heap.timeout_nanos(unit, 0).unwrap(), 0);
            assert_eq!(heap.timeout_nanos(unit, i64::MIN).unwrap(), 0);
            assert_eq!(heap.timeout_nanos(unit, 1).unwrap(), factor);
            assert_eq!(heap.timeout_nanos(unit, i64::MAX).unwrap(), i64::MAX as u64);
        }
        let other = heap.allocate(vec![]).unwrap();
        assert_eq!(heap.timeout_nanos(other, 0), Err("TimeUnit inesperado"));
        assert!(heap.time_unit(7).is_err());
    }
    use super::*;
    use crate::scheduler::WorkerPool;
    use std::sync::Barrier;

    #[test]
    fn default_factory_identity_is_shared_across_threads() {
        let heap = SharedHeap::default();
        let expected = heap.default_forkjoin_factory().unwrap();
        let threads = (0..8)
            .map(|_| {
                let h = heap.clone();
                std::thread::spawn(move || {
                    for _ in 0..100 {
                        assert_eq!(h.default_forkjoin_factory().unwrap(), expected);
                    }
                })
            })
            .collect::<Vec<_>>();
        for thread in threads {
            thread.join().unwrap();
        }
        assert_ne!(
            SharedHeap::default().default_forkjoin_factory().unwrap(),
            expected
        );
    }
    #[test]
    fn workers_update_shared_fields_via_cas_and_wrapping_add() {
        let heap = SharedHeap::default();
        let id = heap
            .allocate(vec![Value::Int(0), Value::Int(i32::MAX), Value::Ref(None)])
            .unwrap();
        let other = heap.allocate(vec![]).unwrap();
        let wrong = SharedHeap::default().allocate(vec![]).unwrap();
        assert!(heap
            .compare_exchange(id, 2, Value::Ref(None), Value::Ref(Some(wrong)))
            .is_err());
        assert_eq!(
            heap.compare_exchange(id, 2, Value::Ref(None), Value::Ref(Some(other))),
            Ok(true)
        );
        assert_eq!(
            heap.compare_exchange(id, 2, Value::Ref(None), Value::Ref(None)),
            Ok(false)
        );
        assert_eq!(heap.get_and_add_int(id, 1, 1), Ok(i32::MAX));
        assert_eq!(heap.read(id, 1), Ok(Value::Int(i32::MIN)));
        let pool = WorkerPool::new(4).unwrap();
        for _ in 0..4 {
            let h = heap.clone();
            pool.execute(move || {
                for _ in 0..1000 {
                    loop {
                        let Value::Int(old) = h.read(id, 0).unwrap() else {
                            panic!("tipo")
                        };
                        if h.compare_exchange(id, 0, Value::Int(old), Value::Int(old + 1))
                            .unwrap()
                        {
                            break;
                        }
                    }
                }
            })
            .unwrap();
        }
        assert_eq!(pool.shutdown(), Ok(0));
        assert_eq!(heap.read(id, 0), Ok(Value::Int(4000)));
    }

    #[test]
    fn workers_share_reentrant_monitor_and_fields() {
        let heap = SharedHeap::default();
        let id = heap
            .allocate(vec![Value::Int(0), Value::Ref(None)])
            .unwrap();
        let pool = WorkerPool::new(4).unwrap();
        let start = Arc::new(Barrier::new(5));
        for _ in 0..4 {
            let (h, gate) = (heap.clone(), Arc::clone(&start));
            pool.execute(move || {
                gate.wait();
                for _ in 0..1000 {
                    let _outer = h.enter(id).unwrap();
                    let _inner = h.enter(id).unwrap();
                    let Value::Int(v) = h.read(id, 0).unwrap() else {
                        panic!("tipo")
                    };
                    h.write(id, 0, Value::Int(v + 1)).unwrap();
                }
            })
            .unwrap();
        }
        start.wait();
        assert_eq!(pool.shutdown(), Ok(0));
        assert_eq!(heap.read(id, 0), Ok(Value::Int(4000)));
        assert!(heap.write(id, 0, Value::Ref(None)).is_err());
        assert!(heap.read(id, 2).is_err());
        assert!(heap
            .enter(ObjectId {
                heap: id.heap,
                index: 999
            })
            .is_err());
        let other = SharedHeap::default();
        let other_id = other.allocate(vec![Value::Int(0)]).unwrap();
        assert!(heap.read(other_id, 0).is_err());
        assert!(heap.write(id, 1, Value::Ref(Some(other_id))).is_err());
        assert!(heap.allocate(vec![Value::Ref(Some(other_id))]).is_err());
    }
}
