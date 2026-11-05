//! Primera conexión AOT del bytecode real con frames y heap compartido.
//! Perfil deliberadamente pequeño: enteros, llamadas, objetos final muy limitados
//! y estáticos volatile/final; <clinit> reducido y anticipado. La variante Rayon
//! soporta un perfil restringido de ForkJoinPool; no implementa excepciones Java.
use super::{
    bytecode, class_from_jar, find_method_inner, metadata, method_ref, object, CpEntry, Result,
};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

/// Opt-in unificado de futuros (Q-AB-2). El nombre canonico es
/// `MC_AOT_FUTURES=restricted`; el historico `MC_AOT_RAYON_COMPLETED_FUTURE=1` sigue
/// valiendo como alias una version. Un valor desconocido se rechaza en vez de
/// adivinarse, para que una errata no active el perfil por accidente.
/// Opt-in de referencias mutables (Q-AB-1). Sin el, un campo de referencia no
/// `final` sigue rechazandose: una referencia compartida y escribible sin reglas
/// seria semantica inventada. Con el, la escritura pasa por el mutex del heap, el
/// destino debe estar publicado y ser de la clase esperada, y un campo `final`
/// sigue sin admitir escrituras fuera del constructor.
fn mutable_refs_optin() -> bool {
    std::env::var_os("MC_AOT_RAYON_MUTABLE_REFS").as_deref() == Some(std::ffi::OsStr::new("1"))
}

fn futures_restricted_optin() -> Result<bool> {
    match std::env::var("MC_AOT_FUTURES") {
        Ok(v) if v == "restricted" => Ok(true),
        Ok(v) if v == "off" => Ok(false),
        Ok(v) => Err(format!(
            "futuros: valor de MC_AOT_FUTURES no soportado: {v} (admitidos: off, restricted)"
        )),
        Err(_) => Ok(
            std::env::var_os("MC_AOT_RAYON_COMPLETED_FUTURE").as_deref()
                == Some(std::ffi::OsStr::new("1")),
        ),
    }
}

fn arg_count(desc: &str) -> Result<usize> {
    let futures = futures_restricted_optin()?;
    match desc {
        "()I" | "()V" | "()Ljava/util/concurrent/ExecutorService;" => Ok(0),
        "(I)I"
        | "(I)V"
        | "(J)I"
        | "(J)V"
        | "(Ljava/util/concurrent/ForkJoinPool;)V"
        | "(Ljava/lang/Throwable;)V"
        | "(Ljava/util/concurrent/ExecutorService;)V"
        | "(Ljava/lang/String;)V"
        | "(Ljava/util/concurrent/atomic/AtomicInteger;)V"
        | "(Ljava/lang/Runnable;)V"
        | "(Ljava/lang/Runnable;)Ljava/lang/Runnable;"
        | "(Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;" => {
            Ok(1)
        }
        "(JLjava/util/concurrent/TimeUnit;)V"
        | "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;)V"
        | "(Ljava/lang/String;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;" => Ok(2),
        "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;Ljava/lang/String;)V" | "(Ljava/util/concurrent/atomic/AtomicInteger;Ljava/lang/String;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;" | "(Ljava/lang/String;Ljava/util/concurrent/atomic/AtomicInteger;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;" => Ok(3),
        "(Ljava/util/concurrent/CompletableFuture;)V" if futures => Ok(1),
        "(ILjava/lang/Runnable;)V" if std::env::var_os("MC_AOT_RAYON_PROJECT_REFERENCES").as_deref()==Some(std::ffi::OsStr::new("1")) => Ok(2),
        _ if std::env::var_os("MC_AOT_RAYON_PROJECT_REFERENCES").as_deref()==Some(std::ffi::OsStr::new("1"))
            && desc.strip_prefix("(Lnet/minecraft/").and_then(|x|x.strip_suffix(";)V"))
                .is_some_and(|name|!name.is_empty() && !name.chars().any(|c|matches!(c,';'|'['|'('|')'))) => Ok(1),
        _ => Err(format!("concurrent-int: firma no soportada: {desc}")),
    }
}

fn verify_hash(data: &[u8], expected: &str, error: &str) -> Result<()> {
    use std::io::Write;
    let mut hash = std::process::Command::new("sha256sum")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;
    hash.stdin
        .take()
        .ok_or("sin stdin sha256sum")?
        .write_all(data)
        .map_err(|e| e.to_string())?;
    let digest = hash.wait_with_output().map_err(|e| e.to_string())?;
    if !digest.status.success()
        || !String::from_utf8_lossy(&digest.stdout).starts_with(&format!("{expected} "))
    {
        return Err(error.into());
    }
    Ok(())
}
struct Builder<'a> {
    data: Vec<u8>,
    jar: &'a Path,
    class: &'a str,
    fields: BTreeMap<String, (usize, String, bool)>,
    methods: Vec<(String, String, String, bool)>,
    compiled: Vec<String>,
    synchronized: Vec<u8>,
    local_counts: Vec<usize>,
    runnable: BTreeMap<String, usize>,
    factories: BTreeMap<String, (usize, String, usize, usize, usize)>,
    executors: BTreeSet<String>,
    executor_methods: BTreeMap<String, usize>,
    executor_dispatch: bool,
    rayon: bool,
}
impl Builder<'_> {
    fn project_reference(&self, descriptor: &str) -> Result<Option<String>> {
        if !self.rayon || std::env::var_os("MC_AOT_RAYON_PROJECT_REFERENCES").as_deref()!=Some(std::ffi::OsStr::new("1")) {return Ok(None);}
        let Some(klass)=descriptor.strip_prefix('L').and_then(|s|s.strip_suffix(';')) else {return Ok(None)};
        if !klass.starts_with("net/minecraft/") || klass.contains(';') || klass.contains('[') {return Ok(None)}
        let data=class_from_jar(self.jar,klass)?;let meta=metadata::parse(&data)?;
        if meta.name!=klass || meta.flags&0x10==0 || meta.flags&0x0200!=0 || meta.parent.as_deref()!=Some("java/lang/Object") || !meta.interfaces.is_empty() || meta.methods.iter().any(|m|m.name=="<clinit>") {return Err(format!("concurrent-int: referencia requiere clase final directa sin interfaces ni inicializador: {klass}"));}
        Ok(Some(klass.to_owned()))
    }
    fn field_is_final(&self, owner: &str, field: &str) -> Result<bool> {
        let data = class_from_jar(self.jar, owner)?;
        let meta = metadata::parse(&data)?;
        meta.fields
            .iter()
            .find(|f| f.name == field && f.flags & 8 == 0)
            .map(|f| f.flags & 0x10 != 0)
            .ok_or_else(|| format!("concurrent-int: campo de instancia inexistente: {owner}.{field}"))
    }

    fn object_fields(&self, owner: &str) -> Result<Vec<(String, String)>> {
        let data = class_from_jar(self.jar, owner)?;
        let meta = metadata::parse(&data)?;
        let factory = self.rayon
            && meta.parent.as_deref() == Some("java/lang/Object")
            && meta.interfaces.as_slice()
                == ["java/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory"]
            && {
                let instance = meta
                    .fields
                    .iter()
                    .filter(|f| f.flags & 8 == 0)
                    .collect::<Vec<_>>();
                instance.is_empty()
                    || (instance.len() == 1
                        && instance[0].flags & 0x10 != 0
                        && matches!(
                            instance[0].descriptor.as_str(),
                            "Ljava/util/concurrent/atomic/AtomicInteger;" | "Ljava/lang/String;"
                        ))
            };
        let worker = self.rayon
            && meta.parent.as_deref() == Some("java/util/concurrent/ForkJoinWorkerThread")
            && meta.interfaces.is_empty()
            && {
                let instance = meta
                    .fields
                    .iter()
                    .filter(|f| f.flags & 8 == 0)
                    .collect::<Vec<_>>();
                instance.len() <= 2
                    && instance
                        .iter()
                        .all(|f| f.flags & 0x10 != 0 && f.descriptor == "Ljava/lang/String;")
            };
        let normal = meta.parent.as_deref() == Some("java/lang/Object")
            && (meta.interfaces.is_empty()
                || (self.rayon
                    && (meta.interfaces.as_slice() == ["java/lang/Runnable"]
                        || meta.interfaces.as_slice() == ["java/util/concurrent/Executor"])));
        let record = self.rayon
            && meta.parent.as_deref() == Some("java/lang/Record")
            && (meta.interfaces.is_empty()
                || meta.interfaces.as_slice() == ["java/util/concurrent/Executor"]);
        // The official anonymous worker is not final. Permit only these exact
        // bytes; the closed profile still rejects arbitrary non-final classes.
        let official_worker = self.rayon && owner == "net/minecraft/util/Util$2";
        if official_worker {
            verify_hash(
                &data,
                "0324db47427384d1dfe3e0e9f61410121af90931d9267f08ec85bc6f164cb205",
                "Util$2: versión de clase no verificada",
            )?;
        }
        let tick_task=self.rayon && owner=="net/minecraft/server/TickTask" && std::env::var_os("MC_AOT_RAYON_PROJECT_REFERENCES").as_deref()==Some(std::ffi::OsStr::new("1"));
        if tick_task {verify_hash(&data,"dae918ab7da617b85384411773b9759ffbc0c0609bfc06c7dc4af85b76fa69b6","TickTask: versión de clase no verificada")?;}
        if meta.name != owner
            || (meta.flags & 0x10 == 0 && !official_worker && !tick_task)
            || meta.flags & 0x0200 != 0
            || !(factory || worker || normal || record)
            || meta.methods.iter().any(|m| m.name == "<clinit>")
        {
            return Err(format!("concurrent-int: objeto requiere clase final sin inicializador ni jerarquía: {owner}"));
        }
        let mut fields = Vec::new();
        for field in meta.fields.iter().filter(|f| f.flags & 8 == 0) {
            let project=self.project_reference(&field.descriptor)?;
            let future=self.rayon && field.descriptor=="Ljava/util/concurrent/CompletableFuture;" && futures_restricted_optin()?;
            if future && field.flags&0x10==0 {return Err(format!("concurrent-int: captura CompletableFuture debe ser final: {owner}.{}",field.name));}
            if project.is_some() && field.flags&0x10==0 && !mutable_refs_optin() {return Err(format!("concurrent-int: captura de referencia debe ser final: {owner}.{}",field.name));}
            if field.descriptor != "I" && project.is_none() && !future && !(tick_task && field.descriptor=="Ljava/lang/Runnable;" && field.flags&0x10!=0)
                && !(self.rayon
                    && matches!(
                        field.descriptor.as_str(),
                        "Ljava/util/concurrent/ExecutorService;"
                            | "Ljava/util/concurrent/atomic/AtomicInteger;"
                            | "Ljava/lang/String;"
                    ))
            {
                return Err(format!(
                    "concurrent-int: campo de instancia no int: {owner}.{}",
                    field.name
                ));
            }
            fields.push((field.name.clone(), field.descriptor.clone()));
        }
        Ok(fields)
    }
    fn pure_external_class(&self, owner: &str) -> Result<()> {
        if !owner.starts_with("net/minecraft/") {
            return Err(format!(
                "concurrent-int: llamada externa no soportada: {owner}"
            ));
        }
        let data = class_from_jar(self.jar, owner)?;
        if self.rayon && owner == "net/minecraft/TracingExecutor" {
            self.object_fields(owner)?;
            return Ok(());
        }
        let meta = metadata::parse(&data)?;
        if meta.name != owner
            || meta.parent.as_deref() != Some("java/lang/Object")
            || !meta.interfaces.is_empty()
            || meta.flags & 0x0200 != 0
            || meta.methods.iter().any(|m| m.name == "<clinit>")
        {
            return Err(format!(
                "concurrent-int: clase externa con inicializador o jerarquía: {owner}"
            ));
        }
        Ok(())
    }
    fn is_runnable(&self, owner: &str) -> Result<bool> {
        let data = class_from_jar(self.jar, owner)?;
        let meta = metadata::parse(&data)?;
        Ok(meta.interfaces.as_slice() == ["java/lang/Runnable"])
    }
    fn is_executor(&self, owner: &str) -> Result<bool> {
        let data = class_from_jar(self.jar, owner)?;
        let meta = metadata::parse(&data)?;
        Ok(meta.interfaces.as_slice() == ["java/util/concurrent/Executor"])
    }
    fn is_worker_class(&self, owner: &str) -> Result<bool> {
        if matches!(
            owner,
            "java/lang/Thread" | "java/util/concurrent/ForkJoinWorkerThread"
        ) {
            return Ok(true);
        }
        let data = class_from_jar(self.jar, owner)?;
        let meta = metadata::parse(&data)?;
        Ok(meta.parent.as_deref() == Some("java/util/concurrent/ForkJoinWorkerThread"))
    }
    fn is_factory(&self, owner: &str) -> Result<bool> {
        let data = class_from_jar(self.jar, owner)?;
        let meta = metadata::parse(&data)?;
        Ok(meta.interfaces.as_slice()
            == ["java/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory"])
    }
    fn register_factory(&mut self, owner: &str) -> Result<()> {
        let data = class_from_jar(self.jar, owner)?;
        let desc =
            "(Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;";
        let method = find_method_inner(&data, "newThread", desc, true, false, false)?;
        let code = &method.code;
        if !method.handlers.is_empty() {
            return Err("concurrent-int: factory Java no trivial".into());
        }
        let (new_offset, ctor_offset, with_name, renamed) = if code.len() == 9
            && code[0] == 0xbb
            && code[3] == 0x59
            && code[4] == 0x2b
            && code[5] == 0xb7
            && code[8] == 0xb0
        {
            (0, 5, false, false)
        } else if (code.len() == 13 || code.len() == 23)
            && code[0] == 0xbb
            && code[3] == 0x59
            && code[4] == 0x2b
            && code[5] == 0x2a
            && code[6] == 0xb4
            && code[9] == 0xb7
            && ((code.len() == 13 && code[12] == 0xb0)
                || (code.len() == 23
                    && code[12] == 0x4d
                    && code[13] == 0x2c
                    && code[14] == 0x2a
                    && code[15] == 0xb4
                    && code[18] == 0xb6
                    && code[21] == 0x2c
                    && code[22] == 0xb0))
        {
            let (field_owner, field_name, field_type) =
                object::field_ref(&method.cp, u16::from_be_bytes([code[7], code[8]]))?;
            let metadata = metadata::parse(&data)?;
            let fields = metadata
                .fields
                .iter()
                .filter(|f| f.flags & 8 == 0)
                .collect::<Vec<_>>();
            if field_owner != owner
                || field_type != "Ljava/lang/String;"
                || fields.len() != 1
                || fields[0].name != field_name
                || fields[0].flags & 0x10 == 0
            {
                return Err("concurrent-int: factory Java no trivial".into());
            }
            if code.len() == 23 {
                let second =
                    object::field_ref(&method.cp, u16::from_be_bytes([code[16], code[17]]))?;
                if second != (field_owner, field_name, field_type) {
                    return Err("concurrent-int: factory Java no trivial".into());
                }
            }
            (0, 9, true, code.len() == 23)
        } else if code.len() == 17
            && code[0] == 0x2a
            && code[1] == 0xb4
            && code[4] == 0xb6
            && code[7] == 0x57
            && code[8] == 0xbb
            && code[11] == 0x59
            && code[12] == 0x2b
            && code[13] == 0xb7
            && code[16] == 0xb0
        {
            let (field_owner, field_name, field_type) =
                object::field_ref(&method.cp, u16::from_be_bytes([code[2], code[3]]))?;
            let (atomic, call, signature) =
                method_ref(&method.cp, u16::from_be_bytes([code[5], code[6]]))?;
            let meta = metadata::parse(&data)?;
            let fields = meta
                .fields
                .iter()
                .filter(|f| f.flags & 8 == 0)
                .collect::<Vec<_>>();
            if field_owner != owner
                || field_type != "Ljava/util/concurrent/atomic/AtomicInteger;"
                || fields.len() != 1
                || fields[0].name != field_name
                || fields[0].flags & 0x10 == 0
                || atomic != "java/util/concurrent/atomic/AtomicInteger"
                || call != "getAndIncrement"
                || signature != "()I"
            {
                return Err("concurrent-int: factory Java no trivial".into());
            }
            (8, 13, false, false)
        } else {
            return Err("concurrent-int: factory Java no trivial".into());
        };
        let worker = object::class_name(
            &method.cp,
            u16::from_be_bytes([code[new_offset + 1], code[new_offset + 2]]),
        )?
        .to_owned();
        let (callee, ctor, signature) = method_ref(
            &method.cp,
            u16::from_be_bytes([code[ctor_offset + 1], code[ctor_offset + 2]]),
        )?;
        if callee != worker
            || ctor != "<init>"
            || signature
                != if with_name {
                    "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;)V"
                } else {
                    "(Ljava/util/concurrent/ForkJoinPool;)V"
                }
        {
            return Err("concurrent-int: factory Java no trivial".into());
        }
        if renamed {
            let (target, method_name, descriptor) =
                method_ref(&method.cp, u16::from_be_bytes([code[19], code[20]]))?;
            if !matches!(
                target,
                "java/lang/Thread" | "java/util/concurrent/ForkJoinWorkerThread"
            ) && target != worker
                || method_name != "setName"
                || descriptor != "(Ljava/lang/String;)V"
            {
                return Err("concurrent-int: factory Java no trivial".into());
            }
        }
        let (start, end) = self.register_worker(&worker, usize::from(with_name))?;
        let create = self.register(owner, "newThread", desc, true)?;
        self.factories
            .insert(owner.to_owned(), (create, worker, start, end, 0));
        Ok(())
    }
    fn register_worker(&mut self, worker: &str, names: usize) -> Result<(usize, usize)> {
        self.object_fields(worker)?;
        let bytes = class_from_jar(self.jar, worker)?;
        let meta = metadata::parse(&bytes)?;
        if meta
            .methods
            .iter()
            .any(|m| m.name == "run" || m.name == "start")
        {
            return Err("concurrent-int: worker con override run/start no soportado".into());
        }
        if meta.parent.as_deref() != Some("java/util/concurrent/ForkJoinWorkerThread") {
            return Err("concurrent-int: worker Java no soportado".into());
        }
        let init = find_method_inner(
            &bytes,
            "<init>",
            match names {
                0 => "(Ljava/util/concurrent/ForkJoinPool;)V",
                1 => "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;)V",
                2 => "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;Ljava/lang/String;)V",
                _ => return Err("constructor worker no soportado".into()),
            },
            true,
            false,
            false,
        )?;
        let c = &init.code;
        let basic = names == 0
            && c.len() == 6
            && c[0] == 0x2a
            && c[1] == 0x2b
            && c[2] == 0xb7
            && c[5] == 0xb1;
        let named = names == 1
            && c.len() == 11
            && c[0] == 0x2a
            && c[1] == 0x2b
            && c[2] == 0xb7
            && c[5] == 0x2a
            && c[6] == 0x2c
            && c[7] == 0xb5
            && c[10] == 0xb1;
        let two_before = names == 2
            && c.len() == 16
            && c[0] == 0x2a
            && c[1] == 0x2c
            && c[2] == 0xb5
            && c[5] == 0x2a
            && c[6] == 0x2d
            && c[7] == 0xb5
            && c[10] == 0x2a
            && c[11] == 0x2b
            && c[12] == 0xb7
            && c[15] == 0xb1;
        let two_after = names == 2
            && c.len() == 16
            && c[0] == 0x2a
            && c[1] == 0x2b
            && c[2] == 0xb7
            && c[5] == 0x2a
            && c[6] == 0x2c
            && c[7] == 0xb5
            && c[10] == 0x2a
            && c[11] == 0x2d
            && c[12] == 0xb5
            && c[15] == 0xb1;
        if !init.handlers.is_empty() || !(basic || named || two_before || two_after) {
            return Err("concurrent-int: constructor worker no trivial".into());
        }
        if two_before || two_after {
            let (a, b) = if two_before { (3, 8) } else { (8, 13) };
            let first = object::field_ref(&init.cp, u16::from_be_bytes([c[a], c[a + 1]]))?;
            let second = object::field_ref(&init.cp, u16::from_be_bytes([c[b], c[b + 1]]))?;
            let fields = meta
                .fields
                .iter()
                .filter(|f| f.flags & 8 == 0)
                .collect::<Vec<_>>();
            if first.0 != worker
                || second.0 != worker
                || first.1 == second.1
                || first.2 != "Ljava/lang/String;"
                || second.2 != "Ljava/lang/String;"
                || fields.len() != 2
                || !fields.iter().all(|f| {
                    f.flags & 0x10 != 0
                        && f.descriptor == "Ljava/lang/String;"
                        && (f.name == first.1 || f.name == second.1)
                })
            {
                return Err("concurrent-int: constructor worker no trivial".into());
            }
        }
        if named {
            let (field_owner, field_name, field_type) =
                object::field_ref(&init.cp, u16::from_be_bytes([c[8], c[9]]))?;
            let fields = meta
                .fields
                .iter()
                .filter(|f| f.flags & 8 == 0)
                .collect::<Vec<_>>();
            if field_owner != worker
                || field_type != "Ljava/lang/String;"
                || fields.len() != 1
                || fields[0].name != field_name
                || fields[0].flags & 0x10 == 0
            {
                return Err("concurrent-int: constructor worker no trivial".into());
            }
        }
        let (superclass, initname, initdesc) = method_ref(
            &init.cp,
            if two_before {
                u16::from_be_bytes([c[13], c[14]])
            } else {
                u16::from_be_bytes([c[3], c[4]])
            },
        )?;
        if superclass != "java/util/concurrent/ForkJoinWorkerThread"
            || initname != "<init>"
            || initdesc != "(Ljava/util/concurrent/ForkJoinPool;)V"
        {
            return Err("concurrent-int: constructor worker no trivial".into());
        }
        let start = self.register(worker, "onStart", "()V", true)?;
        let end = self.register(worker, "onTermination", "(Ljava/lang/Throwable;)V", true)?;
        Ok((start, end))
    }
    fn string_concat(&self, owner: &str, m: &super::Method, index: u16) -> Result<Option<String>> {
        let (bootstrap, nt) = match m.cp.get(index as usize) {
            Some(CpEntry::InvokeDynamic(b, n)) => (*b, *n),
            _ => return Err("invokedynamic inválido".into()),
        };
        let data = if owner == self.class {
            self.data.clone()
        } else {
            class_from_jar(self.jar, owner)?
        };
        let bootstraps = super::bootstrap_methods(&data)?;
        let b = bootstraps
            .get(bootstrap as usize)
            .ok_or("bootstrap inválido")?;
        let target = match m.cp.get(b.method as usize) {
            Some(CpEntry::MethodHandle(6, i)) => *i,
            _ => return Err("bootstrap inválido".into()),
        };
        let (bo, bn, bd) = method_ref(&m.cp, target)?;
        if bo != "java/lang/invoke/StringConcatFactory" {
            return Ok(None);
        }
        if bn!="makeConcatWithConstants" || bd!="(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;Ljava/lang/invoke/MethodType;Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/invoke/CallSite;" || b.arguments.len()!=1 {return Err("concat bootstrap no soportado".into());}
        let (name, desc) = match m.cp.get(nt as usize) {
            Some(CpEntry::NameType(n, d)) => (super::utf(&m.cp, *n)?, super::utf(&m.cp, *d)?),
            _ => return Err("concat NameType inválido".into()),
        };
        if name != "makeConcatWithConstants" || desc != "(Ljava/lang/String;I)Ljava/lang/String;" {
            return Err("concat firma no soportada".into());
        }
        let utf = match m.cp.get(b.arguments[0] as usize) {
            Some(CpEntry::String(i)) => *i,
            _ => return Err("receta concat inválida".into()),
        };
        let units = match m.cp.get(utf as usize) {
            Some(CpEntry::Utf8(u)) => &u.units,
            _ => return Err("receta concat inválida".into()),
        };
        if units.iter().filter(|&&u| u == 1).count() != 2 || units.contains(&2) {
            return Err("receta concat no soportada".into());
        }
        let recipe = units
            .iter()
            .map(|u| format!("{u}u16"))
            .collect::<Vec<_>>()
            .join(",");
        Ok(Some(format!("let number=pop_int(f)?;let text=match f.pop()?{{Value::Ref(value)=>value,_=>return Err(FrameError::Heap(\"concat no String\"))}};let id=heap.concat_string_int(text,number,&[{recipe}])?;f.push(Value::Ref(Some(id)));")))
    }
    fn register_lambda_factory(
        &mut self,
        owner: &str,
        m: &super::Method,
        index: u16,
    ) -> Result<(String, usize)> {
        if !self.rayon || owner != self.class {
            return Err("lambda factory fuera del perfil".into());
        }
        let (bootstrap, nt) = match m.cp.get(index as usize) {
            Some(CpEntry::InvokeDynamic(b, n)) => (*b, *n),
            _ => return Err("lambda factory inválida".into()),
        };
        let (name, factory_desc) = match m.cp.get(nt as usize) {
            Some(CpEntry::NameType(n, d)) => (super::utf(&m.cp, *n)?, super::utf(&m.cp, *d)?),
            _ => return Err("lambda NameType inválido".into()),
        };
        let captures=match factory_desc {
            "(Ljava/lang/String;)Ljava/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory;"=>1,
            "(Ljava/util/concurrent/atomic/AtomicInteger;Ljava/lang/String;)Ljava/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory;"=>2,
            "(Ljava/lang/String;Ljava/util/concurrent/atomic/AtomicInteger;)Ljava/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory;"=>3,
            _=>return Err("lambda factory fuera del perfil".into()),
        };
        if name != "newThread" {
            return Err("lambda factory fuera del perfil".into());
        }
        let bootstraps = super::bootstrap_methods(&self.data)?;
        let b = bootstraps
            .get(bootstrap as usize)
            .ok_or("bootstrap inválido")?;
        let target = match m.cp.get(b.method as usize) {
            Some(CpEntry::MethodHandle(6, i)) => *i,
            _ => return Err("bootstrap factory inválido".into()),
        };
        let (bo, bn, bd) = method_ref(&m.cp, target)?;
        if (bo,bn,bd)!=("java/lang/invoke/LambdaMetafactory","metafactory","(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodHandle;Ljava/lang/invoke/MethodType;)Ljava/lang/invoke/CallSite;") || b.arguments.len()!=3 {return Err("bootstrap factory no soportado".into());}
        let mt = |i: u16| -> Result<&str> {
            match m.cp.get(i as usize) {
                Some(CpEntry::MethodType(n)) => super::utf(&m.cp, *n),
                _ => Err("factory MethodType inválido".into()),
            }
        };
        let sam =
            "(Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;";
        if mt(b.arguments[0])? != sam || mt(b.arguments[2])? != sam {
            return Err("lambda factory SAM no soportado".into());
        }
        let imp = match m.cp.get(b.arguments[1] as usize) {
            Some(CpEntry::MethodHandle(6, i)) => *i,
            _ => return Err("factory MethodHandle no soportado".into()),
        };
        let (imp_owner, imp_name, imp_desc) = method_ref(&m.cp, imp)?;
        let expected = match captures {
            1 => "(Ljava/lang/String;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;",
            2 => "(Ljava/util/concurrent/atomic/AtomicInteger;Ljava/lang/String;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;",
            3 => "(Ljava/lang/String;Ljava/util/concurrent/atomic/AtomicInteger;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;",
            _ => unreachable!(),
        };
        let meta = metadata::parse(&self.data)?;
        if imp_owner != owner
            || imp_desc != expected
            || !meta.methods.iter().any(|m| {
                m.name == imp_name && m.descriptor == imp_desc && m.flags & 0x1008 == 0x1008
            })
        {
            return Err("lambda factory implementación no soportada".into());
        }
        let method = find_method_inner(&self.data, imp_name, imp_desc, true, true, false)?;
        let c = &method.code;
        let (new_offset, ctor_offset, renamed, worker_names) = if captures == 1
            && c.len() == 10
            && c[0] == 0xbb
            && c[3] == 0x59
            && c[4] == 0x2b
            && c[5] == 0x2a
            && c[6] == 0xb7
            && c[9] == 0xb0
        {
            (0, 6, false, 1)
        } else if captures == 2
            && c.len() == 15
            && c[0] == 0x2a
            && c[1] == 0xb6
            && c[4] == 0x57
            && c[5] == 0xbb
            && c[8] == 0x59
            && c[9] == 0x2c
            && c[10] == 0x2b
            && c[11] == 0xb7
            && c[14] == 0xb0
        {
            let (owner, name, desc) = method_ref(&method.cp, u16::from_be_bytes([c[2], c[3]]))?;
            if owner != "java/util/concurrent/atomic/AtomicInteger"
                || name != "getAndIncrement"
                || desc != "()I"
            {
                return Err("lambda factory implementación no soportada".into());
            }
            (5, 11, false, 1)
        } else if captures == 3
            && c.len() == 19
            && c[0] == 0xbb
            && c[3] == 0x59
            && c[4] == 0x2c
            && c[5] == 0x2a
            && c[6] == 0x2b
            && c[7] == 0xb6
            && c[10] == 0xba
            && c[13] == 0
            && c[14] == 0
            && c[15] == 0xb7
            && c[18] == 0xb0
        {
            let (atomic, method_name, desc) =
                method_ref(&method.cp, u16::from_be_bytes([c[8], c[9]]))?;
            if atomic != "java/util/concurrent/atomic/AtomicInteger"
                || method_name != "getAndIncrement"
                || desc != "()I"
                || self
                    .string_concat(&self.class, &method, u16::from_be_bytes([c[11], c[12]]))?
                    .is_none()
            {
                return Err("lambda factory implementación no soportada".into());
            }
            (0, 15, false, 1)
        } else if captures == 3
            && c.len() == 31
            && c[0] == 0x2a
            && c[1] == 0x2b
            && c[2] == 0xb6
            && c[5] == 0xba
            && c[8] == 0
            && c[9] == 0
            && c[10] == 0x4e
            && c[11] == 0xbb
            && c[14] == 0x59
            && c[15] == 0x2c
            && c[16] == 0x2d
            && c[17] == 0xb7
            && c[20] == 0x3a
            && c[21] == 4
            && c[22] == 0x19
            && c[23] == 4
            && c[24] == 0x2d
            && c[25] == 0xb6
            && c[28] == 0x19
            && c[29] == 4
            && c[30] == 0xb0
        {
            let (atomic, call, signature) =
                method_ref(&method.cp, u16::from_be_bytes([c[3], c[4]]))?;
            if atomic != "java/util/concurrent/atomic/AtomicInteger"
                || call != "getAndIncrement"
                || signature != "()I"
                || self
                    .string_concat(&self.class, &method, u16::from_be_bytes([c[6], c[7]]))?
                    .is_none()
            {
                return Err("lambda factory implementación no soportada".into());
            }
            (11, 17, true, 1)
        } else if captures == 3
            && c.len() == 32
            && c[0] == 0x2a
            && c[1] == 0x2b
            && c[2] == 0xb6
            && c[5] == 0xba
            && c[8] == 0
            && c[9] == 0
            && c[10] == 0x4e
            && c[11] == 0xbb
            && c[14] == 0x59
            && c[15] == 0x2c
            && c[16] == 0x2d
            && c[17] == 0x2a
            && c[18] == 0xb7
            && c[21] == 0x3a
            && c[22] == 4
            && c[23] == 0x19
            && c[24] == 4
            && c[25] == 0x2d
            && c[26] == 0xb6
            && c[29] == 0x19
            && c[30] == 4
            && c[31] == 0xb0
        {
            let (atomic, call, signature) =
                method_ref(&method.cp, u16::from_be_bytes([c[3], c[4]]))?;
            if atomic != "java/util/concurrent/atomic/AtomicInteger"
                || call != "getAndIncrement"
                || signature != "()I"
                || self
                    .string_concat(&self.class, &method, u16::from_be_bytes([c[6], c[7]]))?
                    .is_none()
            {
                return Err("lambda factory implementación no soportada".into());
            }
            (11, 18, true, 2)
        } else {
            return Err("lambda factory implementación no soportada".into());
        };
        if !method.handlers.is_empty() {
            return Err("lambda factory implementación no soportada".into());
        }
        let worker = object::class_name(
            &method.cp,
            u16::from_be_bytes([c[new_offset + 1], c[new_offset + 2]]),
        )?
        .to_owned();
        let (target, ctor, descriptor) = method_ref(
            &method.cp,
            u16::from_be_bytes([c[ctor_offset + 1], c[ctor_offset + 2]]),
        )?;
        if target != worker
            || ctor != "<init>"
            || descriptor
                != if worker_names == 2 {
                    "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;Ljava/lang/String;)V"
                } else {
                    "(Ljava/util/concurrent/ForkJoinPool;Ljava/lang/String;)V"
                }
        {
            return Err("lambda factory constructor no soportado".into());
        }
        if renamed {
            let (target, name, desc) = method_ref(
                &method.cp,
                if worker_names == 2 {
                    u16::from_be_bytes([c[27], c[28]])
                } else {
                    u16::from_be_bytes([c[26], c[27]])
                },
            )?;
            if !matches!(
                target,
                "java/lang/Thread" | "java/util/concurrent/ForkJoinWorkerThread"
            ) && target != worker
                || name != "setName"
                || desc != "(Ljava/lang/String;)V"
            {
                return Err("lambda factory implementación no soportada".into());
            }
        }
        let key = format!("mc-aot/lambda-factory/{owner}/{index}");
        if !self.factories.contains_key(&key) {
            let (start, end) = self.register_worker(&worker, worker_names)?;
            let implementation = self.register(imp_owner, imp_name, imp_desc, false)?;
            self.factories.insert(
                key.clone(),
                (
                    implementation,
                    worker,
                    start,
                    end,
                    if captures == 3 { 2 } else { captures },
                ),
            );
        }
        Ok((key, captures))
    }
    fn register(&mut self, owner: &str, name: &str, desc: &str, instance: bool) -> Result<usize> {
        arg_count(desc)?;
        if !self.rayon && desc.starts_with("(J") {
            return Err("concurrent-int: parámetros long requieren Rayon".into());
        }
        if let Some(i) = self
            .methods
            .iter()
            .position(|m| m.0 == owner && m.1 == name && m.2 == desc && m.3 == instance)
        {
            return Ok(i);
        }
        let id = self.methods.len();
        self.methods
            .push((owner.into(), name.into(), desc.into(), instance));
        Ok(id)
    }
    fn compile(&mut self, id: usize) -> Result<()> {
        let (owner, name, desc, instance) = self.methods[id].clone();
        let argc = arg_count(&desc)?;
        let offset = usize::from(instance);
        let required_locals = argc + offset + usize::from(desc.starts_with("(J"));
        let data = if owner == self.class {
            self.data.clone()
        } else {
            class_from_jar(self.jar, &owner)?
        };
        if instance {
            self.object_fields(&owner)?;
        }
        let m = find_method_inner(&data, &name, &desc, true, !instance, true)?;
        let static_slot = m.locals;
        self.local_counts.push(m.locals);
        self.synchronized.push(if !m.synchronized {
            0
        } else if instance {
            2
        } else {
            1
        });
        if !m.handlers.is_empty() {
            // Perfil explícito, solo para el método exacto del JAR oficial: la
            // interrupción Java no existe en este backend. No se afirma que
            // el catch ni las excepciones Java funcionen en general.
            let eligible = self.rayon
                && owner == "net/minecraft/TracingExecutor"
                && name == "shutdownAndAwait"
                && desc == "(JLjava/util/concurrent/TimeUnit;)V"
                && std::env::var_os("MC_AOT_RAYON_ASSUME_NO_INTERRUPT").as_deref()
                    == Some(std::ffi::OsStr::new("1"))
                && m.handlers.len() == 1
                && m.handlers[0].start == 9
                && m.handlers[0].end == 22
                && m.handlers[0].target == 25
                && m.handlers[0].catch_type.as_deref() == Some("java/lang/InterruptedException");
            if !eligible {
                return Err(format!("concurrent-int: handlers no soportados: {name}"));
            }
            verify_hash(
                &data,
                "80786a96dc2259a9c16eeb9c3329400c830c02cc568069581eee4789e62b5e32",
                "TracingExecutor: versión de clase no verificada",
            )?;
        }
        let tracing_unloaded = self.rayon
            && owner == "net/minecraft/TracingExecutor"
            && name == "wrapUnnamed"
            && desc == "(Ljava/lang/Runnable;)Ljava/lang/Runnable;";
        if tracing_unloaded {
            if std::env::var_os("MC_AOT_RAYON_ASSUME_NO_TRACY").as_deref()
                != Some(std::ffi::OsStr::new("1"))
            {
                return Err("TracingExecutor: requiere MC_AOT_RAYON_ASSUME_NO_TRACY=1".into());
            }
            verify_hash(
                &data,
                "80786a96dc2259a9c16eeb9c3329400c830c02cc568069581eee4789e62b5e32",
                "TracingExecutor: versión de clase no verificada",
            )?;
            let tracy = class_from_jar(self.jar, "com/mojang/jtracy/TracyClient")?;
            verify_hash(
                &tracy,
                "55d6a5576bd91504ebdea28af611a243aa5e0b1f288d78241f788e34c0c2f3a1",
                "TracyClient: versión de clase no verificada",
            )?;
        }
        if m.locals < required_locals || m.locals > 256 {
            return Err(format!(
                "concurrent-int: número de locales no soportado: {name}"
            ));
        }
        let bounds = bytecode::scan(&m.code)?.boundaries;
        let mut pc = 0usize;
        let mut arms = String::new();
        let mut edges = Vec::new();
        while pc < m.code.len() {
            let start = pc;
            let op = m.code[pc];
            pc += 1;
            let mut take = || {
                let b = m
                    .code
                    .get(pc)
                    .copied()
                    .ok_or("bytecode truncado".to_string())?;
                pc += 1;
                Ok::<u8, String>(b)
            };
            let mut terminal = false;
            let body = match op {
                0x01 if self.rayon => "f.push(Value::Ref(None));".into(),
                0x09..=0x0a if self.rayon => format!("f.push(Value::Long({}));", op - 0x09),
                0x02..=0x08 => format!("f.push(Value::Int({}));", op as i32 - 3),
                0x10 => format!("f.push(Value::Int({}));", take()? as i8),
                0x11 => {
                    let a = take()?;
                    let b = take()?;
                    format!("f.push(Value::Int({}));", i16::from_be_bytes([a, b]))
                }
                0x12 | 0x13 => {
                    let index = if op == 0x12 {
                        take()? as u16
                    } else {
                        u16::from_be_bytes([take()?, take()?])
                    };
                    match m.cp.get(index as usize) {
                        Some(CpEntry::Integer(v))=>format!("f.push(Value::Int({v}));"),
                        Some(CpEntry::String(utf_index)) if self.rayon=>{
                            let Some(CpEntry::Utf8(value))=m.cp.get(*utf_index as usize) else {return Err("concurrent-int: String inválido".into());};
                            let units=value.units.iter().map(|u|format!("{u}u16")).collect::<Vec<_>>().join(",");
                            format!("let id=heap.intern_string(&[{units}])?;f.push(Value::Ref(Some(id)));")
                        },
                        _=>return Err("concurrent-int: ldc no soportado".into()),
                    }
                }
                0x14 if self.rayon => {
                    let index = u16::from_be_bytes([take()?, take()?]);
                    let Some(CpEntry::Long(v)) = m.cp.get(index as usize) else {
                        return Err("concurrent-int: ldc2 no long".into());
                    };
                    format!("f.push(Value::Long({v}));")
                }
                0x85 if self.rayon => "let a=pop_int(f)?;f.push(Value::Long(a as i64));".into(),
                0x1e..=0x21 | 0x16 if self.rayon => {
                    let local=if op==0x16 {take()? as usize} else {(op-0x1e) as usize};
                    if local+1>=m.locals {return Err("concurrent-int: lload local inválido".into());}
                    format!("let Value::Long(v)=f.locals[{local}] else {{return Err(FrameError::Heap(\"local no long\"));}};f.push(Value::Long(v));")
                }
                0x3f..=0x42 | 0x37 if self.rayon => {
                    let local=if op==0x37 {take()? as usize} else {(op-0x3f) as usize};
                    if local+1>=m.locals {return Err("concurrent-int: lstore local inválido".into());}
                    format!("f.locals[{local}]=Value::Long(pop_long(f)?);f.locals[{}]=Value::Void;",local+1)
                }
                0x1a..=0x1d | 0x15 => {
                    let local = if op == 0x15 {
                        take()? as usize
                    } else {
                        (op - 0x1a) as usize
                    };
                    if local >= m.locals {
                        return Err("concurrent-int: iload local inválido".into());
                    }
                    format!("let Value::Int(v)=f.locals[{local}] else {{return Err(FrameError::Heap(\"local no int\"));}};f.push(Value::Int(v));")
                }
                0x2a..=0x2d | 0x19 => {
                    let local = if op == 0x19 {
                        take()? as usize
                    } else {
                        (op - 0x2a) as usize
                    };
                    if local >= m.locals {
                        return Err("concurrent-int: aload local inválido".into());
                    }
                    format!("let Value::Ref(v)=f.locals[{local}] else {{return Err(FrameError::Heap(\"local no referencia\"));}};f.push(Value::Ref(v));")
                }
                0x3b..=0x3e | 0x36 => {
                    let local = if op == 0x36 {
                        take()? as usize
                    } else {
                        (op - 0x3b) as usize
                    };
                    if local >= m.locals {
                        return Err("concurrent-int: istore local inválido".into());
                    }
                    format!("f.locals[{local}]=Value::Int(pop_int(f)?);")
                }
                0x4b..=0x4e | 0x3a => {
                    let local = if op == 0x3a {
                        take()? as usize
                    } else {
                        (op - 0x4b) as usize
                    };
                    if local >= m.locals {
                        return Err("concurrent-int: astore local inválido".into());
                    }
                    format!("let v=f.pop()?;if !matches!(v,Value::Ref(_)){{return Err(FrameError::Heap(\"se esperaba referencia\"));}}f.locals[{local}]=v;")
                }
                0x57 => "let v=f.pop()?;if matches!(v,Value::Long(_)){return Err(FrameError::Heap(\"pop sobre valor categoría 2\"));}".into(),
                0x59 => "let v=f.pop()?;if matches!(v,Value::Long(_)){return Err(FrameError::Heap(\"dup sobre valor categoría 2\"));}f.push(v);f.push(v);".into(),
                0x60 | 0x64 | 0x68 | 0x7e | 0x80 | 0x82 => {
                    let method = match op {
                        0x60 => "wrapping_add",
                        0x64 => "wrapping_sub",
                        0x68 => "wrapping_mul",
                        0x7e => "bitand",
                        0x80 => "bitor",
                        _ => "bitxor",
                    };
                    if op >= 0x7e {
                        let symbol = match op {
                            0x7e => "&",
                            0x80 => "|",
                            _ => "^",
                        };
                        format!(
                            "let b=pop_int(f)?;let a=pop_int(f)?;f.push(Value::Int(a{symbol}b));"
                        )
                    } else {
                        format!("let b=pop_int(f)?;let a=pop_int(f)?;f.push(Value::Int(a.{method}(b)));")
                    }
                }
                0x78 | 0x7a | 0x7c => {
                    let expr = match op {
                        0x78 => "a.wrapping_shl((b as u32)&31)",
                        0x7a => "a>>((b as u32)&31)",
                        _ => "((a as u32)>>((b as u32)&31)) as i32",
                    };
                    format!("let b=pop_int(f)?;let a=pop_int(f)?;f.push(Value::Int({expr}));")
                }
                0x74 => "let a=pop_int(f)?;f.push(Value::Int(a.wrapping_neg()));".into(),
                0x84 => {
                    let local = take()?;
                    let n = take()? as i8;
                    if local as usize >= m.locals {
                        return Err("concurrent-int: iinc no soportado".into());
                    }
                    format!("let Value::Int(a)=f.locals[{local}] else {{return Err(FrameError::Heap(\"local no int\"));}};f.locals[{local}]=Value::Int(a.wrapping_add({n}));")
                }
                0x99..=0xa4 | 0xa7 => {
                    let delta = i16::from_be_bytes([take()?, take()?]) as isize;
                    let target =
                        usize::try_from(start as isize + delta).map_err(|_| "salto negativo")?;
                    edges.push(target);
                    if op == 0xa7 {
                        terminal = true;
                        format!("f.pc={target};return Ok(Step::Continue);")
                    } else {
                        let (test, pop) = match op {
                            0x99 => ("a==0", "let a=pop_int(f)?;"),
                            0x9a => ("a!=0", "let a=pop_int(f)?;"),
                            0x9b => ("a<0", "let a=pop_int(f)?;"),
                            0x9c => ("a>=0", "let a=pop_int(f)?;"),
                            0x9d => ("a>0", "let a=pop_int(f)?;"),
                            0x9e => ("a<=0", "let a=pop_int(f)?;"),
                            0x9f => ("a==b", "let b=pop_int(f)?;let a=pop_int(f)?;"),
                            0xa0 => ("a!=b", "let b=pop_int(f)?;let a=pop_int(f)?;"),
                            0xa1 => ("a<b", "let b=pop_int(f)?;let a=pop_int(f)?;"),
                            0xa2 => ("a>=b", "let b=pop_int(f)?;let a=pop_int(f)?;"),
                            0xa3 => ("a>b", "let b=pop_int(f)?;let a=pop_int(f)?;"),
                            _ => ("a<=b", "let b=pop_int(f)?;let a=pop_int(f)?;"),
                        };
                        format!("{pop}if {test}{{f.pc={target};return Ok(Step::Continue);}}")
                    }
                }
                0xa5 | 0xa6 if self.rayon => {
                    let delta=i16::from_be_bytes([take()?,take()?]) as isize;
                    let target=usize::try_from(start as isize+delta).map_err(|_|"salto negativo")?;
                    edges.push(target);
                    let condition=if op==0xa5 {"a==b"} else {"a!=b"};
                    format!("let b=match f.pop()?{{Value::Ref(id)=>id,_=>return Err(FrameError::Heap(\"comparación no referencia\"))}};let a=match f.pop()?{{Value::Ref(id)=>id,_=>return Err(FrameError::Heap(\"comparación no referencia\"))}};if {condition}{{f.pc={target};return Ok(Step::Continue);}}")
                }
                0xc6 | 0xc7 if self.rayon => {
                    let delta=i16::from_be_bytes([take()?,take()?]) as isize;
                    let target=usize::try_from(start as isize+delta).map_err(|_|"salto negativo")?;
                    edges.push(target);
                    let condition=if op==0xc6 {"is_null"} else {"!is_null"};
                    format!("let is_null=match f.pop()?{{Value::Ref(id)=>id.is_none(),_=>return Err(FrameError::Heap(\"comparación null no referencia\"))}};if {condition}{{f.pc={target};return Ok(Step::Continue);}}")
                }
                0xb2 | 0xb3 => {
                    let idx = u16::from_be_bytes([take()?, take()?]);
                    let (owner, field, descriptor) = object::field_ref(&m.cp, idx)?;
                    if self.rayon
                        && op == 0xb2
                        && owner == "java/util/concurrent/TimeUnit"
                        && descriptor == "Ljava/util/concurrent/TimeUnit;"
                    {
                        let index = match field {
                            "NANOSECONDS" => 0,
                            "MICROSECONDS" => 1,
                            "MILLISECONDS" => 2,
                            "SECONDS" => 3,
                            "MINUTES" => 4,
                            "HOURS" => 5,
                            "DAYS" => 6,
                            _ => return Err("concurrent-int: TimeUnit no soportado".into()),
                        };
                        format!("let id=heap.time_unit({index})?;f.push(Value::Ref(Some(id)));")
                    } else if self.rayon
                        && op == 0xb2
                        && owner == "java/util/concurrent/ForkJoinPool"
                        && field == "defaultForkJoinWorkerThreadFactory"
                        && descriptor
                            == "Ljava/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory;"
                    {
                        "let id=heap.default_forkjoin_factory()?;f.push(Value::Ref(Some(id)));"
                            .into()
                    } else {
                        if owner != self.class {
                            return Err(format!(
                                "concurrent-int: campo externo no soportado: {owner}.{field}"
                            ));
                        }
                        let (slot, field_desc, is_final) = self
                            .fields
                            .get(field)
                            .ok_or("concurrent-int: campo no volatile")?;
                        if op == 0xb3 && *is_final && name != "<clinit>" {
                            return Err(
                                "concurrent-int: escritura de final fuera de <clinit>".into()
                            );
                        }
                        if field_desc != descriptor {
                            return Err("concurrent-int: descriptor de campo inválido".into());
                        }
                        let check = if descriptor == "I" {
                            "if !matches!(v,Value::Int(_)){return Err(FrameError::Heap(\"campo no int\"));}".to_string()
                        } else if let Some(klass) = descriptor
                            .strip_prefix('L')
                            .and_then(|s| s.strip_suffix(';'))
                        {
                            if !(self.rayon && matches!(klass,"java/util/concurrent/ForkJoinPool"|"java/util/concurrent/atomic/AtomicInteger"|"java/lang/String")) {
                                self.object_fields(klass)?;
                            }
                            format!("match v{{Value::Ref(None)=>{{}},Value::Ref(Some(id)) if heap.class_of(id)?==Some({klass:?})=>{{}},_=>return Err(FrameError::Heap(\"tipo de campo incorrecto\"))}}")
                        } else {
                            return Err(
                                "concurrent-int: tipo de campo estático no soportado".into()
                            );
                        };
                        if op == 0xb2 {
                            format!(
                                "let id=static_id(f,{static_slot})?;f.push(heap.read(id,{slot})?);"
                            )
                        } else {
                            format!("let v=f.pop()?;{check}let id=static_id(f,{static_slot})?;heap.write(id,{slot},v)?;")
                        }
                    }
                }
                0xb9 => {
                    let idx = u16::from_be_bytes([take()?, take()?]);
                    let count = take()?;
                    let zero = take()?;
                    let (klass, callee, descriptor) = method_ref(&m.cp, idx)?;
                    if self.rayon && owner=="net/minecraft/server/TickTask" && name=="run" && klass=="java/lang/Runnable" && callee=="run" && descriptor=="()V" && count==1 && zero==0 && std::env::var_os("MC_AOT_RAYON_PROJECT_REFERENCES").as_deref()==Some(std::ffi::OsStr::new("1")) {
                        terminal=true;format!("let task=pop_any_object(f)?;let method=runnable_method(heap,task)?;f.pc={pc};return Ok(Step::Call{{method,args:vec![Value::Ref(Some(task)),f.locals[{static_slot}]]}});")
                    } else if self.rayon && klass=="java/util/concurrent/ExecutorService" && callee=="shutdownNow" && descriptor=="()Ljava/util/List;" && count==1 && zero==0 {
                        terminal=true;
                        "let _pool=pop_object(f,heap,\"java/util/concurrent/ForkJoinPool\")?;return Err(FrameError::Heap(\"shutdownNow no soportado\"));".into()
                    } else if self.rayon
                        && klass == "java/util/concurrent/ExecutorService"
                        && callee == "shutdown"
                        && descriptor == "()V"
                        && count == 1
                        && zero == 0
                    {
                        terminal = true;
                        format!("let pool=pop_object(f,heap,\"java/util/concurrent/ForkJoinPool\")?;f.pc={pc};return Ok(Step::PoolShutdown{{pool}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ExecutorService"
                        && callee == "awaitTermination"
                        && descriptor == "(JLjava/util/concurrent/TimeUnit;)Z"
                        && count == 4
                        && zero == 0
                    {
                        terminal = true;
                        format!("let unit=pop_any_object(f)?;let timeout=pop_long(f)?;let pool=pop_object(f,heap,\"java/util/concurrent/ForkJoinPool\")?;let nanos=heap.timeout_nanos(unit,timeout)?;f.pc={pc};return Ok(Step::PoolAwait{{pool,nanos}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ExecutorService"
                        && (callee == "isShutdown" || callee == "isTerminated")
                        && descriptor == "()Z"
                        && count == 1
                        && zero == 0
                    {
                        terminal = true;
                        let step = if callee == "isShutdown" {
                            "PoolIsShutdown"
                        } else {
                            "PoolIsTerminated"
                        };
                        format!("let pool=pop_object(f,heap,\"java/util/concurrent/ForkJoinPool\")?;f.pc={pc};return Ok(Step::{step}{{pool}});")
                    } else {
                        if !self.rayon
                            || !matches!(
                                klass,
                                "java/util/concurrent/Executor"
                                    | "java/util/concurrent/ExecutorService"
                            )
                            || callee != "execute"
                            || descriptor != "(Ljava/lang/Runnable;)V"
                            || count != 2
                            || zero != 0
                        {
                            return Err(format!("concurrent-int: invokeinterface no soportado: {klass}.{callee}{descriptor}"));
                        }
                        terminal = true;
                        if klass=="java/util/concurrent/Executor" {
                            self.executor_dispatch=true;
                            format!("let task=f.pop()?;if !matches!(task,Value::Ref(_)){{return Err(FrameError::Heap(\"tarea no referencia\"));}}let receiver=pop_any_object(f)?;f.pc={pc};if heap.class_of(receiver)?==Some(\"java/util/concurrent/ForkJoinPool\"){{let Value::Ref(Some(task))=task else {{return Err(FrameError::Heap(\"tarea nula\"));}};let method=runnable_method(heap,task)?;return Ok(Step::PoolExecute{{pool:receiver,method,args:vec![Value::Ref(Some(task)),f.locals[{static_slot}]]}});}}let method=executor_method(heap,receiver)?;return Ok(Step::Call{{method,args:vec![Value::Ref(Some(receiver)),task,f.locals[{static_slot}]]}});")
                        } else {
                            format!("let task=pop_any_object(f)?;let pool=pop_object(f,heap,\"java/util/concurrent/ForkJoinPool\")?;let method=runnable_method(heap,task)?;f.pc={pc};return Ok(Step::PoolExecute{{pool,method,args:vec![Value::Ref(Some(task)),f.locals[{static_slot}]]}});")
                        }
                    }
                }
                0xb8 => {
                    let idx = u16::from_be_bytes([take()?, take()?]);
                    let (owner, callee, descriptor) = method_ref(&m.cp, idx)?;
                    if self.rayon && owner=="java/util/concurrent/CompletableFuture" && callee=="completedFuture" && descriptor=="(Ljava/lang/Object;)Ljava/util/concurrent/CompletableFuture;" {
                        if !futures_restricted_optin()? {return Err("completedFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1 (o el nombre unificado MC_AOT_FUTURES=restricted)".into());}
                        "let value=match f.pop()?{Value::Ref(v)=>v,_=>return Err(FrameError::Heap(\"completedFuture requiere referencia\"))};let id=heap.completed_future(value)?;f.push(Value::Ref(Some(id)));".into()
                    } else if tracing_unloaded && owner=="com/mojang/jtracy/TracyClient" && callee=="isAvailable" && descriptor=="()Z" {
                        "f.push(Value::Int(0));".into()
                    } else if self.rayon && owner=="com/mojang/jtracy/TracyClient" && callee=="setThreadName" && descriptor=="(Ljava/lang/String;I)V" {
                        if std::env::var_os("MC_AOT_RAYON_ASSUME_NO_TRACY").as_deref()!=Some(std::ffi::OsStr::new("1")) {return Err("TracyClient.setThreadName: requiere MC_AOT_RAYON_ASSUME_NO_TRACY=1".into());}
                        let tracy=class_from_jar(self.jar,"com/mojang/jtracy/TracyClient")?;
                        verify_hash(&tracy,"55d6a5576bd91504ebdea28af611a243aa5e0b1f288d78241f788e34c0c2f3a1","TracyClient: versión de clase no verificada")?;
                        "let _color=pop_int(f)?;match f.pop()? {Value::Ref(None)=>{},Value::Ref(Some(id)) if heap.class_of(id)?==Some(\"java/lang/String\")=>{},_=>return Err(FrameError::Heap(\"nombre Tracy no String\"))};".into()
                    } else if self.rayon
                        && owner == "java/lang/Thread"
                        && callee == "yield"
                        && descriptor == "()V"
                    {
                        "std::thread::yield_now();".into()
                    } else {
                        if owner != self.class {
                            if !self.rayon {
                                return Err(format!(
                                "concurrent-int: llamada externa no soportada: {owner}.{callee}"
                            ));
                            }
                            self.pure_external_class(owner)?;
                        }
                        let n = arg_count(descriptor)?;
                        let child = self.register(owner, callee, descriptor, false)?;
                        terminal = true;
                        format!("let mut args=Vec::with_capacity({n}+1);for _ in 0..{n}{{args.push(f.pop()?);}}args.reverse();args.push(f.locals[{static_slot}]);f.pc={pc};return Ok(Step::Call{{method:{child},args}});")
                    }
                }
                0xba if tracing_unloaded && start==9 => {
                    let _idx=u16::from_be_bytes([take()?,take()?]);
                    if take()?!=0 || take()?!=0 {return Err("invokedynamic inválido".into());}
                    terminal=true;
                    "return Err(FrameError::Heap(\"Tracy activo no soportado\"));".into()
                }
                0xba if self.rayon => {
                    let idx=u16::from_be_bytes([take()?,take()?]);if take()?!=0 || take()?!=0 {return Err("invokedynamic inválido".into());}
                    if let Some(concat)=self.string_concat(&owner,&m,idx)? {concat} else {
                        let (marker,captures)=self.register_lambda_factory(&owner,&m,idx)?;
                        let pop_text="let text=f.pop()?;match text {Value::Ref(None)=>{},Value::Ref(Some(id)) if heap.class_of(id)?==Some(\"java/lang/String\")=>{},_=>return Err(FrameError::Heap(\"captura lambda no String\"))};";
                        let pop_atomic="let atomic=f.pop()?;match atomic {Value::Ref(None)=>{},Value::Ref(Some(id)) if heap.class_of(id)?==Some(\"java/util/concurrent/atomic/AtomicInteger\")=>{},_=>return Err(FrameError::Heap(\"captura lambda no AtomicInteger\"))};";
                        let code=match captures {1=>format!("{pop_text}let fields=vec![text];"),2=>format!("{pop_text}{pop_atomic}let fields=vec![atomic,text];"),3=>format!("{pop_atomic}{pop_text}let fields=vec![text,atomic];"),_=>unreachable!()};
                        format!("{code}let id=heap.allocate_typed({marker:?},fields)?;f.push(Value::Ref(Some(id)));")
                    }
                }
                0xbb => {
                    let idx = u16::from_be_bytes([take()?, take()?]);
                    let klass = object::class_name(&m.cp, idx)?;
                    if self.rayon && klass=="java/util/concurrent/CompletableFuture" {
                        if !futures_restricted_optin()? {return Err("CompletableFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1 (o el nombre unificado MC_AOT_FUTURES=restricted)".into());}
                        format!("let id=heap.allocate_typed({klass:?},vec![])?;f.push(Value::Ref(Some(id)));")
                    } else if self.rayon && klass == "java/util/concurrent/ForkJoinPool" {
                        format!("let id=heap.allocate_typed({klass:?},vec![])?;f.push(Value::Ref(Some(id)));")
                    } else if self.rayon && klass=="java/util/concurrent/atomic/AtomicInteger" {
                        format!("let id=heap.allocate_typed({klass:?},vec![Value::Int(0)])?;f.push(Value::Ref(Some(id)));")
                    } else {
                        let fields = self.object_fields(klass)?;
                        if self.rayon && self.is_factory(klass)? {
                            self.register_factory(klass)?;
                        }
                        if self.rayon && self.is_executor(klass)? { self.executors.insert(klass.to_owned()); }
                        if self.is_runnable(klass)? {
                            let id = self.register(klass, "run", "()V", true)?;
                            self.runnable.insert(klass.to_string(), id);
                        }
                        let defaults = fields.iter().map(|(_,desc)| if desc=="I" {"Value::Int(0)"} else {"Value::Ref(None)"}).collect::<Vec<_>>().join(",");
                        format!("let id=heap.allocate_typed({klass:?},vec![{defaults}])?;f.push(Value::Ref(Some(id)));")
                    }
                }
                0xb4 | 0xb5 => {
                    let idx = u16::from_be_bytes([take()?, take()?]);
                    let (klass, field, descriptor) = object::field_ref(&m.cp, idx)?;
                    let project=self.project_reference(descriptor)?;
                    let future_ref=self.rayon && descriptor=="Ljava/util/concurrent/CompletableFuture;" && futures_restricted_optin()?;
                    if future_ref && op==0xb5 && (owner!=klass || name!="<init>") {return Err("concurrent-int: escritura de CompletableFuture final fuera del constructor".into());}
                    let task_ref=self.rayon && klass=="net/minecraft/server/TickTask" && descriptor=="Ljava/lang/Runnable;" && std::env::var_os("MC_AOT_RAYON_PROJECT_REFERENCES").as_deref()==Some(std::ffi::OsStr::new("1"));
                    if task_ref && op==0xb5 && (owner!=klass || name!="<init>") {return Err("concurrent-int: escritura de Runnable final fuera del constructor".into());}
                    if descriptor != "I" && project.is_none() && !task_ref && !future_ref && !(self.rayon && matches!(descriptor,"Ljava/util/concurrent/ExecutorService;"|"Ljava/util/concurrent/atomic/AtomicInteger;"|"Ljava/lang/String;")) {
                        return Err("concurrent-int: campo de instancia no soportado".into());
                    }
                    if project.is_some() && op==0xb5 && (owner!=klass || name!="<init>") {
                        let final_field = self.field_is_final(klass, field)?;
                        if final_field || !mutable_refs_optin() {
                            return Err("concurrent-int: escritura de captura final fuera del constructor".into());
                        }
                    }
                    let fields = self.object_fields(klass)?;
                    let slot = fields.iter().position(|(name,desc)| name==field && desc==descriptor)
                        .ok_or("concurrent-int: campo de instancia inexistente")?;
                    if op == 0xb4 {
                        format!("let id=pop_object(f,heap,{klass:?})?;f.push(heap.read(id,{slot})?);")
                    } else if descriptor=="I" {
                        format!("let v=Value::Int(pop_int(f)?);let id=pop_object(f,heap,{klass:?})?;heap.write(id,{slot},v)?;")
                    } else if future_ref {
                        format!("let v=f.pop()?;match v {{Value::Ref(None)=>{{}},Value::Ref(Some(id))=>{{heap.future_check(id)?;}},_=>return Err(FrameError::Heap(\"CompletableFuture de campo no soportado\"))}};let id=pop_object(f,heap,{klass:?})?;heap.write(id,{slot},v)?;")
                    } else if task_ref {
                        format!("let v=f.pop()?;match v {{Value::Ref(None)=>{{}},Value::Ref(Some(id))=>{{let _=runnable_method(heap,id)?;}},_=>return Err(FrameError::Heap(\"Runnable de campo no soportado\"))}};let id=pop_object(f,heap,{klass:?})?;heap.write(id,{slot},v)?;")
                    } else {
                        let expected=if let Some(expected)=project.as_deref() {expected} else if descriptor=="Ljava/util/concurrent/ExecutorService;" {"java/util/concurrent/ForkJoinPool"} else if descriptor=="Ljava/lang/String;" {"java/lang/String"} else {"java/util/concurrent/atomic/AtomicInteger"};
                        format!("let v=f.pop()?;match v {{Value::Ref(None)=>{{}},Value::Ref(Some(id)) if heap.class_of(id)?==Some({expected:?})=>{{}},_=>return Err(FrameError::Heap(\"referencia de campo no soportada\"))}};let id=pop_object(f,heap,{klass:?})?;heap.write(id,{slot},v)?;")
                    }
                }
                0xb6 | 0xb7 => {
                    let idx = u16::from_be_bytes([take()?, take()?]);
                    let (klass, callee, descriptor) = method_ref(&m.cp, idx)?;
                    if self.rayon && op==0xb6 && klass=="java/util/concurrent/CompletableFuture" {
                        if !futures_restricted_optin()? {return Err("CompletableFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1 (o el nombre unificado MC_AOT_FUTURES=restricted)".into());}
                        match (callee,descriptor) {
                            ("get"|"join", "()Ljava/lang/Object;") => "let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;f.push(Value::Ref(heap.completed_future_value(id)?));".into(),
                            ("getNow", "(Ljava/lang/Object;)Ljava/lang/Object;") => "let fallback=match f.pop()?{Value::Ref(v)=>v,_=>return Err(FrameError::Heap(\"getNow requiere referencia\"))};let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;f.push(Value::Ref(heap.future_get_now(id,fallback)?));".into(),
                            ("isDone", "()Z") => "let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;f.push(Value::Int(if heap.future_is_done(id)?{1}else{0}));".into(),
                            ("isCancelled"|"isCompletedExceptionally", "()Z") => "let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;heap.future_is_normal(id)?;f.push(Value::Int(0));".into(),
                            ("complete", "(Ljava/lang/Object;)Z") => "let value=match f.pop()?{Value::Ref(v)=>v,_=>return Err(FrameError::Heap(\"complete requiere referencia\"))};let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;f.push(Value::Int(if heap.future_complete(id,value)?{1}else{0}));".into(),
                            ("cancel", "(Z)Z") => "let _=pop_int(f)?;let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;match heap.future_is_done(id)?{true=>f.push(Value::Int(0)),false=>return Err(FrameError::Heap(\"cancel de futuro pendiente no soportado\"))};".into(),
                            _ => return Err(format!("CompletableFuture: operación no soportada: {callee}{descriptor}")),
                        }
                    } else if self.rayon && op==0xb6 && callee=="setName" && descriptor=="(Ljava/lang/String;)V" && ((name=="newThread" && self.is_factory(&owner)?) || self.factories.values().any(|(create,_,_,_,captures)|*create==id && *captures>0)) && self.is_worker_class(klass)? {
                        "let name=pop_object(f,heap,\"java/lang/String\")?;let worker=pop_any_object(f)?;ensure_worker(heap,worker)?;heap.set_worker_name(worker,name)?;".into()
                    } else if self.rayon && op==0xb6 && callee=="getName" && descriptor=="()Ljava/lang/String;" && self.is_worker_class(klass)? {
                        "let worker=pop_any_object(f)?;ensure_worker(heap,worker)?;let name=heap.worker_name(worker)?.ok_or(FrameError::Heap(\"nombre predeterminado de worker no soportado\"))?;f.push(Value::Ref(Some(name)));".into()
                    } else if self.rayon && klass=="java/lang/String" && op==0xb6 && callee=="hashCode" && descriptor=="()I" {
                        format!("let id=pop_object(f,heap,{klass:?})?;f.push(Value::Int(heap.string_hash(id)?));")
                    } else if self.rayon && klass=="java/lang/String" && op==0xb6 && callee=="length" && descriptor=="()I" {
                        format!("let id=pop_object(f,heap,{klass:?})?;f.push(Value::Int(heap.string_length(id)?));")
                    } else if self.rayon && klass=="java/util/concurrent/atomic/AtomicInteger" && op==0xb7 && callee=="<init>" && descriptor=="(I)V" {
                        format!("let value=pop_int(f)?;let id=pop_object(f,heap,{klass:?})?;heap.write(id,0,Value::Int(value))?;")
                    } else if self.rayon && klass=="java/util/concurrent/atomic/AtomicInteger" && op==0xb6 && callee=="getAndIncrement" && descriptor=="()I" {
                        format!("let id=pop_object(f,heap,{klass:?})?;f.push(Value::Int(heap.atomic_get_and_increment(id)?));")
                    } else if self.rayon && klass=="java/util/concurrent/atomic/AtomicInteger" && op==0xb6 && callee=="get" && descriptor=="()I" {
                        format!("let id=pop_object(f,heap,{klass:?})?;let Value::Int(value)=heap.read(id,0)? else {{return Err(FrameError::Heap(\"AtomicInteger dañado\"));}};f.push(Value::Int(value));")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb7
                        && callee == "<init>"
                        && descriptor == "(I)V"
                    {
                        terminal = true;
                        format!("let count=pop_int(f)?;let pool=pop_object(f,heap,{klass:?})?;f.pc={pc};return Ok(Step::PoolCreate{{pool,count}});")
                    } else if self.rayon && klass=="java/util/concurrent/ForkJoinPool" && op==0xb7 && callee=="<init>" && descriptor=="(ILjava/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory;Ljava/lang/Thread$UncaughtExceptionHandler;Z)V" {
                        terminal=true;
                        format!("let mode=pop_int(f)?;let handler=f.pop()?;let factory=pop_any_object(f)?;let count=pop_int(f)?;let pool=pop_object(f,heap,{klass:?})?;if !matches!(mode,0|1)||!matches!(handler,Value::Ref(None)){{return Err(FrameError::Heap(\"handler personalizado no soportado\"));}}f.pc={pc};if heap.class_of(factory)?==Some(\"mc-aot/default-forkjoin-factory\"){{return Ok(Step::PoolCreate{{pool,count}});}}if count!=1||mode!=1{{return Err(FrameError::Heap(\"factory personalizada requiere un worker y async=true\"));}}let (create,worker,start,end,captures)=factory_methods(heap,factory)?;let capture=if captures>0{{let mut values=Vec::new();for i in 0..captures{{values.push(heap.read(factory,i)?);}}Some(values)}}else{{None}};return Ok(Step::PoolCreateCustom{{pool,count,factory,capture,create,worker,start,end,statics:f.locals[{static_slot}]}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb6
                        && callee == "execute"
                        && descriptor == "(Ljava/lang/Runnable;)V"
                    {
                        terminal = true;
                        format!("let task=pop_any_object(f)?;let pool=pop_object(f,heap,{klass:?})?;let method=runnable_method(heap,task)?;f.pc={pc};return Ok(Step::PoolExecute{{pool,method,args:vec![Value::Ref(Some(task)),f.locals[{static_slot}]]}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb6
                        && callee == "submit"
                        && descriptor == "(Ljava/lang/Runnable;)Ljava/util/concurrent/ForkJoinTask;"
                    {
                        terminal = true;
                        format!("let task=pop_any_object(f)?;let pool=pop_object(f,heap,{klass:?})?;let method=runnable_method(heap,task)?;f.pc={pc};return Ok(Step::PoolSubmit{{pool,method,args:vec![Value::Ref(Some(task)),f.locals[{static_slot}]]}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinTask"
                        && op == 0xb6
                        && callee == "join"
                        && descriptor == "()Ljava/lang/Object;"
                    {
                        terminal = true;
                        format!("let task=pop_object(f,heap,{klass:?})?;f.pc={pc};return Ok(Step::TaskJoin{{task}});")
                    } else if self.rayon && klass=="java/util/concurrent/ForkJoinPool" && op==0xb6 && callee=="awaitTermination" && descriptor=="(JLjava/util/concurrent/TimeUnit;)Z" {
                        terminal=true;format!("let unit=pop_any_object(f)?;let timeout=pop_long(f)?;let pool=pop_object(f,heap,{klass:?})?;let nanos=heap.timeout_nanos(unit,timeout)?;f.pc={pc};return Ok(Step::PoolAwait{{pool,nanos}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb6
                        && callee == "shutdown"
                        && descriptor == "()V"
                    {
                        terminal = true;
                        format!("let pool=pop_object(f,heap,{klass:?})?;f.pc={pc};return Ok(Step::PoolShutdown{{pool}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb6
                        && callee == "isShutdown"
                        && descriptor == "()Z"
                    {
                        terminal = true;
                        format!("let pool=pop_object(f,heap,{klass:?})?;f.pc={pc};return Ok(Step::PoolIsShutdown{{pool}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb6
                        && callee == "isTerminated"
                        && descriptor == "()Z"
                    {
                        terminal = true;
                        format!("let pool=pop_object(f,heap,{klass:?})?;f.pc={pc};return Ok(Step::PoolIsTerminated{{pool}});")
                    } else if self.rayon
                        && klass == "java/util/concurrent/ForkJoinPool"
                        && op == 0xb6
                        && callee == "getParallelism"
                        && descriptor == "()I"
                    {
                        terminal = true;
                        format!("let pool=pop_object(f,heap,{klass:?})?;f.pc={pc};return Ok(Step::PoolParallelism{{pool}});")
                    } else if self.rayon && op==0xb7 && klass=="java/util/concurrent/ForkJoinWorkerThread" && callee=="<init>" && descriptor=="(Ljava/util/concurrent/ForkJoinPool;)V" {
                        "let _pool=pop_object(f,heap,\"java/util/concurrent/ForkJoinPool\")?;let _this=pop_any_object(f)?;".into()
                    } else if self.rayon && op==0xb7 && klass=="java/util/concurrent/ForkJoinWorkerThread" && callee=="onStart" && descriptor=="()V" {
                        "let _this=pop_any_object(f)?;".into()
                    } else if self.rayon && op==0xb7 && klass=="java/util/concurrent/ForkJoinWorkerThread" && callee=="onTermination" && descriptor=="(Ljava/lang/Throwable;)V" {
                        "let _cause=f.pop()?;let _this=pop_any_object(f)?;".into()
                    } else if self.rayon
                        && klass == "java/util/concurrent/CompletableFuture"
                        && op == 0xb7
                        && callee == "<init>"
                        && descriptor == "()V"
                    {
                        if !futures_restricted_optin()? {return Err("CompletableFuture: requiere MC_AOT_RAYON_COMPLETED_FUTURE=1 (o el nombre unificado MC_AOT_FUTURES=restricted)".into());}
                        "let id=pop_object(f,heap,\"java/util/concurrent/CompletableFuture\")?;heap.mark_pending_future(id)?;".into()
                    } else if self.rayon && op==0xb7 && klass=="java/lang/Record" && callee=="<init>" && descriptor=="()V" {
                        "let _this=pop_any_object(f)?;".into()
                    } else if op == 0xb7
                        && klass == "java/lang/Object"
                        && callee == "<init>"
                        && descriptor == "()V"
                    {
                        "let _=f.pop()?;".into()
                    } else {
                        if (op == 0xb7) != (callee == "<init>") {
                            return Err("concurrent-int: invokespecial no constructor".into());
                        }
                        self.object_fields(klass)?;
                        let n = arg_count(descriptor)?;
                        let child = self.register(klass, callee, descriptor, true)?;
                        terminal = true;
                        format!("let mut values=Vec::with_capacity({n});for _ in 0..{n}{{values.push(f.pop()?);}}values.reverse();let id=pop_object(f,heap,{klass:?})?;let mut args=vec![Value::Ref(Some(id))];args.extend(values);args.push(f.locals[{static_slot}]);f.pc={pc};return Ok(Step::Call{{method:{child},args}});")
                    }
                }
                0xb0 => {
                    let executor_return=self.rayon && desc=="()Ljava/util/concurrent/ExecutorService;";
                    if desc!="(Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;" && !(tracing_unloaded && desc=="(Ljava/lang/Runnable;)Ljava/lang/Runnable;") && !executor_return && !(self.rayon && matches!(desc.as_str(),"(Ljava/lang/String;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;"|"(Ljava/util/concurrent/atomic/AtomicInteger;Ljava/lang/String;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;"|"(Ljava/lang/String;Ljava/util/concurrent/atomic/AtomicInteger;Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;")) {return Err("concurrent-int: areturn no soportado".into())}
                    terminal = true;
                    if executor_return {
                        "let v=f.pop()?;match v {Value::Ref(None)=>{},Value::Ref(Some(id)) if heap.class_of(id)?==Some(\"java/util/concurrent/ForkJoinPool\")=>{},_=>return Err(FrameError::Heap(\"retorno ExecutorService no soportado\"))};return Ok(Step::Return(v));".into()
                    } else {
                        "let v=f.pop()?;if !matches!(v,Value::Ref(_)){return Err(FrameError::Heap(\"retorno no referencia\"));}return Ok(Step::Return(v));".into()
                    }
                }
                0xb1 => {
                    if !desc.ends_with('V') {
                        return Err("concurrent-int: return void en método no void".into());
                    }
                    terminal = true;
                    "return Ok(Step::ReturnVoid);".into()
                }
                0xac => {
                    if !desc.ends_with('I') {
                        return Err("concurrent-int: ireturn en método no int".into());
                    }
                    terminal = true;
                    "return Ok(Step::Return(Value::Int(pop_int(f)?)));".into()
                }
                _ => {
                    return Err(format!(
                        "concurrent-int: opcode 0x{op:02x} no soportado en {name}:{start}"
                    ))
                }
            };
            if !terminal {
                edges.push(pc);
                arms.push_str(&format!("{start}=>{{{body}f.pc={pc};Ok(Step::Continue)}},"));
            } else {
                arms.push_str(&format!("{start}=>{{{body}}},"));
            }
        }
        for e in edges {
            if !bounds.contains(&e) {
                return Err(format!("concurrent-int: salto inválido {e}"));
            }
        }
        self.compiled.push(format!("fn method_{id}(heap:&SharedHeap,f:&mut Frame)->std::result::Result<Step,FrameError>{{match f.pc{{{arms}_=>Err(FrameError::InvalidMethod)}}}}"));
        Ok(())
    }
}
pub fn compile(jar: &Path, class: &str, method: &str, desc: &str, rayon: bool) -> Result<String> {
    let data = class_from_jar(jar, class)?;
    let meta = metadata::parse(&data)?;
    if meta.name != class
        || meta.parent.as_deref() != Some("java/lang/Object")
        || !meta.interfaces.is_empty()
        || meta.flags & 0x0200 != 0
    {
        return Err("concurrent-int: jerarquía o clase no soportada".into());
    }
    if desc != "(I)I" {
        return Err("concurrent-int: entrada requiere (I)I".into());
    }
    let mut fields = BTreeMap::new();
    let mut initial = Vec::new();
    for f in &meta.fields {
        if f.flags & 0x0008 != 0 && (f.flags & 0x0040 != 0 || f.flags & 0x0010 != 0) {
            let initial_value = if f.descriptor == "I" {
                let val = match f.constant {
                    None => 0,
                    Some(metadata::ConstantValue::Integer(n)) => n,
                    _ => return Err("concurrent-int: constante inválida".into()),
                };
                Some(format!("Value::Int({val})"))
            } else if f.descriptor.starts_with('L')
                && f.descriptor.ends_with(';')
                && f.constant.is_none()
            {
                Some("Value::Ref(None)".to_owned())
            } else {
                None
            };
            if let Some(value) = initial_value {
                fields.insert(
                    f.name.clone(),
                    (initial.len(), f.descriptor.clone(), f.flags & 0x0010 != 0),
                );
                initial.push(value);
            }
        }
    }
    let mut b = Builder {
        data,
        jar,
        class,
        fields,
        methods: vec![],
        compiled: vec![],
        synchronized: vec![],
        local_counts: vec![],
        runnable: BTreeMap::new(),
        factories: BTreeMap::new(),
        executors: BTreeSet::new(),
        executor_methods: BTreeMap::new(),
        executor_dispatch: false,
        rayon,
    };
    b.register(class, method, desc, false)?;
    let clinit = if meta
        .methods
        .iter()
        .any(|m| m.name == "<clinit>" && m.descriptor == "()V")
    {
        Some(b.register(class, "<clinit>", "()V", false)?)
    } else {
        None
    };
    let mut id = 0;
    loop {
        while id < b.methods.len() {
            if id >= 256 {
                return Err("concurrent-int: demasiados métodos".into());
            }
            b.compile(id)?;
            id += 1;
        }
        if b.executor_dispatch {
            let pending = b
                .executors
                .iter()
                .filter(|name| !b.executor_methods.contains_key(*name))
                .cloned()
                .collect::<Vec<_>>();
            for name in pending {
                let method = b.register(&name, "execute", "(Ljava/lang/Runnable;)V", true)?;
                b.executor_methods.insert(name, method);
            }
        }
        if id == b.methods.len() {
            break;
        }
    }
    let functions = b.compiled.join("\n");
    let methods = (0..b.methods.len())
        .map(|i| format!("method_{i} as NativeStep"))
        .collect::<Vec<_>>()
        .join(",");
    let synchronized = b
        .synchronized
        .iter()
        .map(u8::to_string)
        .collect::<Vec<_>>()
        .join(",");
    let layouts = b
        .local_counts
        .iter()
        .map(usize::to_string)
        .collect::<Vec<_>>()
        .join(",");
    let runnable = b
        .runnable
        .iter()
        .map(|(name, id)| format!("Some({name:?})=>Ok({id}),"))
        .collect::<String>();
    let executor_methods = b
        .executor_methods
        .iter()
        .map(|(name, id)| format!("Some({name:?})=>Ok({id}),"))
        .collect::<String>();
    let worker_names = b
        .factories
        .values()
        .map(|(_, name, _, _, _)| name.clone())
        .collect::<BTreeSet<_>>()
        .iter()
        .map(|name| format!("Some({name:?})=>Ok(()),"))
        .collect::<String>();
    let factories = b
        .factories
        .iter()
        .map(|(name, (create, worker, start, end, is_lambda))| {
            format!("Some({name:?})=>Ok(({create},{worker:?},{start},{end},{is_lambda})),")
        })
        .collect::<String>();
    let executor_runtime = include_str!("executor_runtime.rs");
    let heap = include_str!("concurrent_heap.rs");
    let scheduler = if rayon {
        include_str!("rayon_scheduler.rs")
    } else {
        include_str!("scheduler.rs")
    };
    let frame = include_str!("frame_vm.rs");
    let defaults = initial.join(",");
    let initialize = if let Some(id) = clinit {
        format!("match program.run_with_executors(&heap,{id},vec![Value::Ref(Some(statics))],1_000_000,Some(executors.clone())){{Ok(Value::Void)=>{{}},other=>{{eprintln!(\"falló <clinit>: {{other:?}}\");std::process::exit(2);}}}}")
    } else {
        String::new()
    };
    Ok(format!(
        r#"#![allow(dead_code,unused_variables,unused_mut)]
mod concurrent_heap {{{heap}}}
mod scheduler {{{scheduler}}}
mod frame_vm {{{frame}}}
mod executor_runtime {{{executor_runtime}}}
use executor_runtime::Executors;
use concurrent_heap::{{SharedHeap,Value,ObjectId}};use scheduler::WorkerPool;use frame_vm::{{Program,Frame,FrameError,Step,NativeStep}};use std::sync::Arc;
fn pop_int(f:&mut Frame)->std::result::Result<i32,FrameError>{{match f.pop()?{{Value::Int(v)=>Ok(v),_=>Err(FrameError::Heap("se esperaba int"))}}}}
fn pop_long(f:&mut Frame)->std::result::Result<i64,FrameError>{{match f.pop()?{{Value::Long(v)=>Ok(v),_=>Err(FrameError::Heap("se esperaba long"))}}}}
fn pop_object(f:&mut Frame,heap:&SharedHeap,class:&str)->std::result::Result<ObjectId,FrameError>{{match f.pop()?{{Value::Ref(Some(id)) if heap.class_of(id)?==Some(class)=>Ok(id),_=>Err(FrameError::Heap("receptor nulo o clase inesperada"))}}}}
fn pop_any_object(f:&mut Frame)->std::result::Result<ObjectId,FrameError>{{match f.pop()?{{Value::Ref(Some(id))=>Ok(id),_=>Err(FrameError::Heap("se esperaba referencia no nula"))}}}}
fn ensure_worker(heap:&SharedHeap,id:ObjectId)->std::result::Result<(),FrameError>{{match heap.class_of(id)?{{{worker_names}_=>Err(FrameError::Heap("worker no precompilado"))}}}}
fn executor_method(heap:&SharedHeap,id:ObjectId)->std::result::Result<usize,FrameError>{{match heap.class_of(id)?{{{executor_methods}_=>Err(FrameError::Heap("Executor no precompilado"))}}}}
fn runnable_method(heap:&SharedHeap,id:ObjectId)->std::result::Result<usize,FrameError>{{match heap.class_of(id)?{{{runnable}_=>Err(FrameError::Heap("Runnable no precompilado"))}}}}
fn factory_methods(heap:&SharedHeap,id:ObjectId)->std::result::Result<(usize,&'static str,usize,usize,usize),FrameError>{{match heap.class_of(id)?{{{factories}_=>Err(FrameError::Heap("factory Java no precompilada"))}}}}
fn static_id(f:&Frame,index:usize)->std::result::Result<ObjectId,FrameError>{{match f.locals.get(index){{Some(Value::Ref(Some(id)))=>Ok(*id),_=>Err(FrameError::Heap("estáticos no disponibles"))}}}}
{functions}
fn main(){{let args:Vec<String>=std::env::args().skip(1).collect();let heap=SharedHeap::default();let statics=heap.allocate(vec![{defaults}]).unwrap();let program=Arc::new(Program::with_layouts(vec![{methods}],vec![{synchronized}],vec![{layouts}]));let executors=Arc::new(Executors::default());{initialize}let pool=WorkerPool::new(4).expect("no se pudo crear pool");for phase in args.split(|s|s=="--phase"){{let mut handles=Vec::new();for arg in phase{{let arg:i32=arg.parse().expect("argumento int inválido");let p=program.clone();let h=heap.clone();let e=executors.clone();handles.push(pool.submit(move || p.run_with_executors(&h,0,vec![Value::Int(arg),Value::Ref(Some(statics))],1_000_000,Some(e))).unwrap());}}for handle in handles{{match handle.get(){{Ok(Ok(Value::Int(v)))=>println!("{{v}}"),other=>{{eprintln!("ejecución concurrent-int: {{other:?}}");std::process::exit(2);}}}}}}}}pool.shutdown().expect("falló el pool");}}
"#
    ))
}
