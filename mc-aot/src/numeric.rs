//! AOT de primitivas JVM int/long con pila categorizada. No es un verificador JVM.
use super::{
    bytecode, class_from_jar, find_method_with_handlers, method_ref, CpEntry, Method, Result,
};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

#[derive(Debug, Clone)]
struct Sig {
    args: Vec<char>,
    ret: char,
}
// Minúsculas: arrays primitivos; T: String; t: String[].
// Opt-in unificado de futuros (Q-AB-2/Q-AC-9, decidido el 2026-11-07). El nombre
// canónico es `MC_AOT_FUTURES=restricted` — el que B honra en su backend desde
// `504994b` y el que B publica en su rama — porque describe un perfil (todos los
// futuros tan restringidos como el completed-only) y no caduca si el perfil crece.
// `completed-only` se conserva como alias histórico del mismo perfil y `off` lo
// apaga explícitamente; `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` sigue valiendo como
// alias heredado una versión. La variable vacía cae al alias heredado, igual que no
// estar definida. Un valor desconocido se rechaza: no se ignora en silencio ni se
// adivina la intención. Habilitar `restricted` aquí no habilita futuros pendientes:
// este perfil solo modela futuros ya completados con normalidad, igual que B los
// modela para su backend.
fn futures_optin() -> Result<bool> {
    static CACHE: std::sync::OnceLock<std::result::Result<bool, String>> = std::sync::OnceLock::new();
    CACHE
        .get_or_init(|| match std::env::var("MC_AOT_FUTURES") {
            Ok(value) if value == "restricted" || value == "completed-only" => Ok(true),
            Ok(value) if value == "off" => Ok(false),
            Ok(value) if value.is_empty() => {
                // Variable vacía se comporta como no definida: vale el alias heredado
                // `MC_AOT_NUMERIC_COMPLETED_FUTURE=1` (una versión, Q-AC-7).
                Ok(std::env::var_os("MC_AOT_NUMERIC_COMPLETED_FUTURE").as_deref() == Some(std::ffi::OsStr::new("1")))
            }
            Ok(value) => Err(format!("MC_AOT_FUTURES: valor no soportado: {value} (admitidos: restricted, completed-only, off)")),
            Err(_) => {
                // Alias heredado por defecto: `MC_AOT_NUMERIC_COMPLETED_FUTURE=1`.
                Ok(std::env::var_os("MC_AOT_NUMERIC_COMPLETED_FUTURE").as_deref() == Some(std::ffi::OsStr::new("1")))
            }
        })
        .clone()
}

fn is_ref(t: char) -> bool {
    matches!(
        t,
        'i' | 'j' | 'f' | 'd' | 'z' | 'b' | 'c' | 's' | 'T' | 't' | 'o' | 'a'
    )
}
fn signature(desc: &str) -> Result<Sig> {
    signature_ext(desc, false)
}
fn signature_ext(desc: &str, objects: bool) -> Result<Sig> {
    let (args, ret) = desc
        .strip_prefix('(')
        .and_then(|x| x.split_once(')'))
        .ok_or("descriptor inválido")?;
    let ret = if ret == "Ljava/lang/String;" {
        'T'
    } else if objects && generic_ref(ret) {
        'o'
    } else if objects && ret == "[Ljava/lang/String;" {
        't'
    } else if objects
        && (matches!(ret, "[Ljava/lang/Object;" | "[Ljava/lang/Class;")
            || matches!(super::metadata::field_descriptor(ret),Ok(super::metadata::Type::Array(inner)) if !matches!(*inner,super::metadata::Type::Int|super::metadata::Type::Long|super::metadata::Type::Float|super::metadata::Type::Double|super::metadata::Type::Byte|super::metadata::Type::Char|super::metadata::Type::Short|super::metadata::Type::Boolean)))
    {
        'a'
    } else if objects && ret.len() == 2 && ret.starts_with('[') && "IJFDZBCS".contains(&ret[1..]) {
        ret.as_bytes()[1].to_ascii_lowercase() as char
    } else if objects && matches!(ret, "F" | "D") {
        ret.chars().next().unwrap()
    } else if ret.len() == 1 && "IZBCSJV".contains(ret) {
        ret.chars().next().unwrap()
    } else {
        return Err("retorno no soportado".into());
    };
    let mut types = Vec::new();
    let mut rest = args;
    while !rest.is_empty() {
        if objects {
            if let Some(x) = rest
                .strip_prefix("[Ljava/lang/Object;")
                .or_else(|| rest.strip_prefix("[Ljava/lang/Class;"))
            {
                types.push('a');
                rest = x;
                continue;
            }
        }
        if objects && rest.starts_with("[L") {
            let end = rest.find(';').ok_or("array de referencia truncado")?;
            if matches!(super::metadata::field_descriptor(&rest[..=end]),Ok(super::metadata::Type::Array(inner)) if !matches!(*inner,super::metadata::Type::Int|super::metadata::Type::Long|super::metadata::Type::Float|super::metadata::Type::Double|super::metadata::Type::Byte|super::metadata::Type::Char|super::metadata::Type::Short|super::metadata::Type::Boolean))
            {
                types.push('a');
                rest = &rest[end + 1..];
                continue;
            }
        }
        if let Some(x) = rest.strip_prefix("[Ljava/lang/String;") {
            types.push('t');
            rest = x;
            continue;
        }
        if let Some(x) = rest.strip_prefix("Ljava/lang/String;") {
            types.push('T');
            rest = x;
            continue;
        }
        if objects && rest.starts_with('L') {
            let end = rest.find(';').ok_or("referencia truncada")?;
            let desc = &rest[..=end];
            if generic_ref(desc) {
                types.push('o');
                rest = &rest[end + 1..];
                continue;
            }
        }
        let b = rest.as_bytes()[0];
        if b == b'[' {
            let e = *rest.as_bytes().get(1).ok_or("descriptor array truncado")?;
            if !b"IJZBCS".contains(&e) && !(objects && b"FD".contains(&e)) {
                return Err("solo arrays primitivos o String[] unidimensionales".into());
            }
            types.push((e as char).to_ascii_lowercase());
            rest = &rest[2..];
        } else if objects && b"FD".contains(&b) {
            types.push(b as char);
            rest = &rest[1..];
        } else if b"IJZBCS".contains(&b) {
            types.push(b as char);
            rest = &rest[1..];
        } else {
            return Err("solo argumentos primitivos, String o String[]".into());
        }
    }
    Ok(Sig { args: types, ret })
}
// Recursos Java ServiceLoader: comentarios, CR/LF, trim y duplicados.
// Nombres no ASCII o sintaxis no reconocida son una guarda diferida, no un proveedor ficticio.
fn parse_service_resources(resources: &[Vec<u8>]) -> Vec<String> {
    let mut seen = BTreeSet::new();
    let mut out = Vec::new();
    for bytes in resources {
        let Ok(text) = std::str::from_utf8(bytes) else {
            out.push("!recurso-no-soportado".into());
            continue;
        };
        let mut local = Vec::new();
        let mut valid = true;
        for line in text.split(['\r', '\n']) {
            let name = line
                .split('#')
                .next()
                .unwrap()
                .trim_matches(|c: char| c <= '\u{20}');
            if name.is_empty() {
                continue;
            }
            let b = name.as_bytes();
            if !name.is_ascii()
                || !(b[0].is_ascii_alphabetic() || matches!(b[0], b'_' | b'$'))
                || !b
                    .iter()
                    .skip(1)
                    .all(|c| c.is_ascii_alphanumeric() || matches!(*c, b'_' | b'$' | b'.'))
            {
                valid = false;
                break;
            }
            local.push(name.replace('.', "/"));
        }
        if !valid {
            out.push("!recurso-no-soportado".into());
            continue;
        }
        for name in local {
            if seen.insert(name.clone()) {
                out.push(name);
            }
        }
    }
    out
}
fn project_class(name: &str) -> bool {
    // El JAR/bundle es la fuente de clases; JDK y clases internas del runtime
    // requieren equivalentes explícitos, no se reinterpretan como dependencias.
    !["java/", "javax/", "jdk/", "sun/", "com/sun/"]
        .iter()
        .any(|prefix| name.starts_with(prefix))
}
fn jdk_function_interface(name: &str) -> bool {
    matches!(
        name,
        "java/lang/Runnable"
            | "java/security/PrivilegedAction"
            | "java/util/concurrent/Callable"
            | "java/util/function/Function"
            | "java/util/function/BiFunction"
            | "java/util/function/BinaryOperator"
            | "java/util/function/Supplier"
            | "java/util/function/Consumer"
            | "java/util/function/BiConsumer"
            | "java/util/function/Predicate"
            | "java/util/function/UnaryOperator"
            | "java/util/function/BooleanSupplier"
            | "java/util/function/IntUnaryOperator"
            | "java/util/function/LongUnaryOperator"
            | "java/util/function/ToIntFunction"
            | "java/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory"
            | "java/lang/Thread$UncaughtExceptionHandler"
            | "java/util/concurrent/Executor"
            | "java/util/concurrent/ThreadFactory"
            | "java/util/function/LongSupplier"
            | "java/util/function/IntSupplier"
            | "java/util/function/IntFunction"
            | "java/util/function/ObjIntConsumer"
            | "java/util/function/IntPredicate"
            | "java/util/function/DoubleSupplier"
            | "java/util/function/BiPredicate"
            | "java/util/Comparator"
    )
}
fn jdk_function_method(owner: &str, name: &str, desc: &str) -> bool {
    matches!(
        (owner, name, desc),
        ("java/lang/Runnable", "run", "()V")
            | ("java/util/concurrent/Executor", "execute", "(Ljava/lang/Runnable;)V")
            | ("java/util/concurrent/ThreadFactory", "newThread", "(Ljava/lang/Runnable;)Ljava/lang/Thread;")
            | ("java/util/function/LongSupplier", "getAsLong", "()J")
            | ("java/util/function/IntSupplier", "getAsInt", "()I")
            | ("java/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory", "newThread", "(Ljava/util/concurrent/ForkJoinPool;)Ljava/util/concurrent/ForkJoinWorkerThread;")
            | ("java/lang/Thread$UncaughtExceptionHandler", "uncaughtException", "(Ljava/lang/Thread;Ljava/lang/Throwable;)V")
            | (
                "java/security/PrivilegedAction",
                "run",
                "()Ljava/lang/Object;"
            )
            | (
                "java/util/concurrent/Callable",
                "call",
                "()Ljava/lang/Object;"
            )
            | (
                "java/util/function/Function",
                "apply",
                "(Ljava/lang/Object;)Ljava/lang/Object;"
            )
            | (
                "java/util/function/UnaryOperator",
                "apply",
                "(Ljava/lang/Object;)Ljava/lang/Object;"
            )
            | (
                "java/util/function/BiFunction" | "java/util/function/BinaryOperator",
                "apply",
                "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;"
            )
            | ("java/util/function/Supplier", "get", "()Ljava/lang/Object;")
            | ("java/util/Comparator", "compare", "(Ljava/lang/Object;Ljava/lang/Object;)I")
            | ("java/util/function/BooleanSupplier", "getAsBoolean", "()Z")
            | (
                "java/util/function/Consumer",
                "accept",
                "(Ljava/lang/Object;)V"
            )
            | (
                "java/util/function/BiConsumer",
                "accept",
                "(Ljava/lang/Object;Ljava/lang/Object;)V"
            )
            | (
                "java/util/function/Predicate",
                "test",
                "(Ljava/lang/Object;)Z"
            )
            | (
                "java/util/function/Predicate",
                "negate",
                "()Ljava/util/function/Predicate;"
            )
            | ("java/util/function/IntUnaryOperator", "applyAsInt", "(I)I")
            | ("java/util/function/LongUnaryOperator", "applyAsLong", "(J)J")
            | (
                "java/util/function/ToIntFunction",
                "applyAsInt",
                "(Ljava/lang/Object;)I"
            )
            | ("java/util/function/IntFunction", "apply", "(I)Ljava/lang/Object;")
            | ("java/util/function/ObjIntConsumer", "accept", "(Ljava/lang/Object;I)V")
            | ("java/util/function/IntPredicate", "test", "(I)Z")
            | ("java/util/function/DoubleSupplier", "getAsDouble", "()D")
            | (
                "java/util/function/BiPredicate",
                "test",
                "(Ljava/lang/Object;Ljava/lang/Object;)Z",
            )
            | ("java/nio/file/PathMatcher", "matches", "(Ljava/nio/file/Path;)Z")
            | ("java/util/function/DoubleUnaryOperator", "applyAsDouble", "(D)D")
    )
}
// Equivalentes monohilo concretos, no despacho general de interfaces.
fn collection_intrinsic(owner: &str, name: &str, desc: &str) -> Option<&'static str> {
    let map = matches!(
        owner,
        "java/util/Map"
            | "java/util/HashMap"
            | "java/util/IdentityHashMap"
            | "java/util/TreeMap"
            | "java/util/LinkedHashMap"
            | "java/util/concurrent/ConcurrentMap"
            | "java/util/concurrent/ConcurrentHashMap"
    );
    let queue = matches!(
        owner,
        "java/util/Queue"
            | "java/util/Deque"
            | "java/util/ArrayDeque"
            | "java/util/concurrent/BlockingQueue"
            | "java/util/concurrent/LinkedBlockingQueue"
            | "java/util/concurrent/ConcurrentLinkedQueue"
    );
    let list = matches!(owner, "java/util/List" | "java/util/ArrayList");
    let set = matches!(
        owner,
        "java/util/Set"
            | "java/util/HashSet"
            | "java/util/LinkedHashSet"
            | "java/util/EnumSet"
            | "java/util/concurrent/ConcurrentHashMap$KeySetView"
            | "java/util/TreeSet"
    );
    let common = owner == "java/util/Collection" || queue || list || set;
    match (map,queue,list,common,name,desc) {
        (true,_,_,_,"get","(Ljava/lang/Object;)Ljava/lang/Object;")=>Some("let k=pop_r(&mut stack);let m=pop_r(&mut stack);stack.push(V::R(map_get(heap,m,k)));"),
        (true,_,_,_,"put","(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")=>Some("let v=pop_r(&mut stack);let k=pop_r(&mut stack);let m=pop_r(&mut stack);stack.push(V::R(map_put(heap,m,k,v,false)));"),
        (true,_,_,_,"putIfAbsent","(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")=>Some("let v=pop_r(&mut stack);let k=pop_r(&mut stack);let m=pop_r(&mut stack);stack.push(V::R(map_put(heap,m,k,v,true)));"),
        (true,_,_,_,"remove","(Ljava/lang/Object;)Ljava/lang/Object;")=>Some("let k=pop_r(&mut stack);let m=pop_r(&mut stack);stack.push(V::R(map_remove(heap,m,k)));"),
        (true,_,_,_,"containsKey","(Ljava/lang/Object;)Z")=>Some("let k=pop_r(&mut stack);let m=pop_r(&mut stack);stack.push(V::I(map_contains(heap,m,k) as i32));"),
        (true,_,_,_,"entrySet","()Ljava/util/Set;")=>Some("let m=pop_r(&mut stack);stack.push(V::R(Some(tree_entry_set(heap,m))));"),
        (true,_,_,_,"values","()Ljava/util/Collection;")=>Some("let r=pop_r(&mut stack);stack.push(V::R(Some(map_values(heap,r))));"),
        (true,_,_,_,"size","()I")=>Some("let m=pop_r(&mut stack);stack.push(V::I(map_size(heap,m)));"),
        (true,_,_,_,"isEmpty","()Z")=>Some("let m=pop_r(&mut stack);stack.push(V::I((map_size(heap,m)==0) as i32));"),
        (true,_,_,_,"clear","()V")=>Some("let m=pop_r(&mut stack);map_clear(heap,m);"),
        (_,true,_,_,"addFirst"|"push","(Ljava/lang/Object;)V")=>Some("let v=pop_r(&mut stack);let q=pop_r(&mut stack);deque_add_first(heap,q,v);"),
        (_,true,_,_,"addLast","(Ljava/lang/Object;)V")=>Some("let v=pop_r(&mut stack);let q=pop_r(&mut stack);queue_offer(heap,q,v);"),
        (_,true,_,_,"pop"|"removeFirst","()Ljava/lang/Object;")=>Some("let q=pop_r(&mut stack);let v=deque_take(heap,q,true,true);stack.push(V::R(v));"),
        (_,true,_,_,"removeLast","()Ljava/lang/Object;")=>Some("let q=pop_r(&mut stack);let v=deque_take(heap,q,false,true);stack.push(V::R(v));"),
        (_,true,_,_,"pollFirst","()Ljava/lang/Object;")=>Some("let q=pop_r(&mut stack);let v=deque_take(heap,q,true,false);stack.push(V::R(v));"),
        (_,true,_,_,"pollLast","()Ljava/lang/Object;")=>Some("let q=pop_r(&mut stack);let v=deque_take(heap,q,false,false);stack.push(V::R(v));"),
        (_,true,_,_,"drainTo","(Ljava/util/Collection;I)I")=>Some("let max=pop_i(&mut stack);let dst=pop_r(&mut stack);let src=pop_r(&mut stack);stack.push(V::I(queue_drain_to(heap,src,dst,max)));"),
        (_,true,_,_,"offer","(Ljava/lang/Object;)Z")=>Some("let v=pop_r(&mut stack);let q=pop_r(&mut stack);queue_offer(heap,q,v);stack.push(V::I(1));"),
        (_,true,_,_,"poll","()Ljava/lang/Object;")=>Some("let q=pop_r(&mut stack);stack.push(V::R(queue_poll(heap,q,true)));"),
        (_,true,_,_,"peek","()Ljava/lang/Object;")=>Some("let q=pop_r(&mut stack);stack.push(V::R(queue_poll(heap,q,false)));"),
        (_,_,true,_,"indexOf","(Ljava/lang/Object;)I")=>Some("let v=pop_r(&mut stack);let l=pop_r(&mut stack);stack.push(V::I(list_index_of(heap,l,v)));"),
        (_,_,true,_,"toString","()Ljava/lang/String;")=>Some("let l=pop_r(&mut stack);stack.push(V::R(Some(list_to_string(heap,l))));"),
        (_,_,true,_,"get","(I)Ljava/lang/Object;")=>Some("let i=pop_i(&mut stack);let l=pop_r(&mut stack);stack.push(V::R(list_get(heap,l,i)));"),
        (_,_,true,_,"set","(ILjava/lang/Object;)Ljava/lang/Object;")=>Some("let v=pop_r(&mut stack);let i=pop_i(&mut stack);let l=pop_r(&mut stack);stack.push(V::R(list_set(heap,l,i,v)));"),
        (_,_,true,_,"remove","(I)Ljava/lang/Object;")=>Some("let i=pop_i(&mut stack);let l=pop_r(&mut stack);stack.push(V::R(list_remove(heap,l,i)));"),
        (_,_,_,true,"iterator","()Ljava/util/Iterator;")=>Some("let r=pop_r(&mut stack);stack.push(V::R(Some(collection_iterator(heap,r))));"),
        (_,_,_,true,"addAll","(Ljava/util/Collection;)Z")=>Some("let source=pop_r(&mut stack);let target=pop_r(&mut stack);stack.push(V::I(collection_add_all(heap,target,source) as i32));"),
        (_,_,_,true,"add","(Ljava/lang/Object;)Z")=>Some("let v=pop_r(&mut stack);let c=pop_r(&mut stack);stack.push(V::I(collection_add(heap,c,v) as i32));"),
        (_,_,true,_,"contains","(Ljava/lang/Object;)Z")=>Some("let v=pop_r(&mut stack);let l=pop_r(&mut stack);stack.push(V::I(list_contains(heap,l,v) as i32));"),
        (_,_,_,true,"contains","(Ljava/lang/Object;)Z") if set || owner=="java/util/Collection"=>Some("let v=pop_r(&mut stack);let s=pop_r(&mut stack);stack.push(V::I(set_contains(heap,s,v) as i32));"),
        (_,_,_,true,"remove","(Ljava/lang/Object;)Z") if set || owner=="java/util/Collection"=>Some("let v=pop_r(&mut stack);let s=pop_r(&mut stack);stack.push(V::I(set_remove(heap,s,v) as i32));"),
        (_,_,_,true,"size","()I")=>Some("let c=pop_r(&mut stack);stack.push(V::I(collection_size(heap,c)));"),
        (_,_,_,true,"isEmpty","()Z")=>Some("let c=pop_r(&mut stack);stack.push(V::I((collection_size(heap,c)==0) as i32));"),
        (_,_,_,true,"clear","()V")=>Some("let c=pop_r(&mut stack);collection_clear(heap,c);"),
        _=>None,
    }
}
fn project_array(desc: &str) -> Option<&str> {
    let c = desc.strip_prefix("[L")?.strip_suffix(';')?;
    if project_class(c) {
        Some(c)
    } else {
        None
    }
}
fn generic_ref(desc: &str) -> bool {
    matches!(
        super::metadata::field_descriptor(desc),
        Ok(super::metadata::Type::Object(_))
    )
}
fn rt(t: char) -> &'static str {
    if t == 'V' {
        "()"
    } else if is_ref(t) {
        "Option<usize>"
    } else if t == 'J' {
        "i64"
    } else if t == 'F' {
        "f32"
    } else if t == 'D' {
        "f64"
    } else {
        "i32"
    }
}
fn variant(t: char) -> &'static str {
    if is_ref(t) {
        "R"
    } else if t == 'J' {
        "L"
    } else if t == 'F' {
        "F"
    } else if t == 'D' {
        "D"
    } else {
        "I"
    }
}
fn pop(t: char) -> &'static str {
    if is_ref(t) {
        "pop_r"
    } else if t == 'J' {
        "pop_l"
    } else if t == 'F' {
        "pop_f"
    } else if t == 'D' {
        "pop_d"
    } else {
        "pop_i"
    }
}
fn target(start: usize, offset: i64) -> Result<usize> {
    usize::try_from((start as i64).checked_add(offset).ok_or("overflow salto")?)
        .map_err(|_| "salto negativo".into())
}

fn jdk_exception_parent(name: &str) -> Option<&'static str> {
    Some(match name {
        "java/security/NoSuchAlgorithmException" => "java/security/GeneralSecurityException",
        "java/security/GeneralSecurityException" => "java/lang/Exception",
        "java/security/cert/CertificateException" => "java/security/GeneralSecurityException",
        "java/nio/charset/CharacterCodingException" => "java/io/IOException",
        "java/nio/charset/MalformedInputException" => "java/nio/charset/CharacterCodingException",
        "java/nio/charset/UnmappableCharacterException" => "java/nio/charset/CharacterCodingException",
        _ => return None,
    })
}

fn known_exception(t: &str) -> Option<&'static str> {
    Some(match t {
        "java/lang/Throwable" => "Throwable",
        "java/lang/Error" => "Error",
        "java/lang/AssertionError" => "AssertionError",
        "java/lang/VirtualMachineError" => "VirtualMachineError",
        "java/lang/StackOverflowError" => "StackOverflowError",
        "java/lang/OutOfMemoryError" => "OutOfMemoryError",
        "java/lang/InternalError" => "InternalError",
        "java/lang/LinkageError" => "LinkageError",
        "java/lang/ExceptionInInitializerError" => "ExceptionInInitializerError",
        "java/lang/NoClassDefFoundError" => "NoClassDefFoundError",
        "java/lang/SecurityException" => "SecurityException",
        "java/lang/IllegalMonitorStateException" => "IllegalMonitorStateException",
        "java/lang/ReflectiveOperationException" => "ReflectiveOperationException",
        "java/lang/ClassNotFoundException" => "ClassNotFoundException",
        "java/lang/NoSuchMethodException" => "NoSuchMethodException",
        "java/lang/InstantiationException" => "InstantiationException",
        "java/lang/IllegalAccessException" => "IllegalAccessException",
        "java/lang/reflect/InvocationTargetException" => "InvocationTargetException",

        "java/lang/Exception" => "Exception",
        "java/lang/InterruptedException" => "InterruptedException",
        "java/lang/RuntimeException" => "RuntimeException",
        "java/net/URISyntaxException" => "URISyntaxException",
        "java/io/IOException" => "IOException",
        "java/io/EOFException" => "EOFException",
        "java/io/FileNotFoundException" => "FileNotFoundException",
        "java/nio/file/FileSystemException" => "FileSystemException",
        "java/nio/file/NoSuchFileException" => "NoSuchFileException",
        "java/nio/file/AccessDeniedException" => "AccessDeniedException",
        "java/io/UncheckedIOException" => "UncheckedIOException",
        "java/time/DateTimeException" => "DateTimeException",
        "java/lang/UnsupportedOperationException" => "UnsupportedOperationException",
        "java/util/ServiceConfigurationError" => "ServiceConfigurationError",
        "java/util/NoSuchElementException" => "NoSuchElementException",
        "java/util/ConcurrentModificationException" => "ConcurrentModificationException",
        "java/lang/IllegalArgumentException" => "IllegalArgumentException",
        "java/lang/IllegalStateException" => "IllegalStateException",
        "java/lang/IllegalCallerException" => "IllegalCallerException",
        "java/lang/MatchException" => "MatchException",
        "java/util/concurrent/CancellationException" => "CancellationException",
        "java/lang/NumberFormatException" => "NumberFormatException",
        "java/lang/IndexOutOfBoundsException" => "IndexOutOfBoundsException",
        "java/lang/ArithmeticException" => "ArithmeticException",
        "java/lang/NullPointerException" => "NullPointerException",
        "java/lang/ArrayIndexOutOfBoundsException" => "ArrayIndexOutOfBoundsException",
        "java/lang/StringIndexOutOfBoundsException" => "StringIndexOutOfBoundsException",
        "java/lang/NegativeArraySizeException" => "NegativeArraySizeException",
        "java/lang/ClassCastException" => "ClassCastException",
        "java/lang/ArrayStoreException" => "ArrayStoreException",
        "java/net/MalformedURLException" => "MalformedURLException",
        "java/net/ProtocolException" => "ProtocolException",
        "java/nio/charset/MalformedInputException" => "MalformedInputException",
        _ => return None,
    })
}

// Perfil Java 25: getSecurityManager es null y el cargador de clases del bundle no lo es.
// Solo pliega patrones inmediatos con predecesores únicos; los handlers agregan
// aristas conservadoras y toda otra entrada al patrón impide la optimización.
fn profile_reachable(m: &Method) -> Result<Option<BTreeSet<usize>>> {
    use std::collections::{BTreeMap, VecDeque};
    let summary = bytecode::scan(&m.code)?;
    let mut order = summary.boundaries.iter().copied().collect::<Vec<_>>();
    order.sort_unstable();
    let mut next = BTreeMap::new();
    for (i, p) in order.iter().enumerate() {
        next.insert(*p, order.get(i + 1).copied().unwrap_or(m.code.len()));
    }
    if order.iter().any(|&p| {
        matches!(m.code[p], 0xa8 | 0xa9 | 0xc9)
            || m.code[p] == 0xc4 && m.code.get(p + 1) == Some(&0xa9)
    }) {
        return Ok(None);
    }
    let mut edges: BTreeMap<usize, BTreeSet<usize>> = BTreeMap::new();
    for &p in &order {
        let op = m.code[p];
        let mut dest = BTreeSet::new();
        let fall = next[&p];
        if matches!(op, 0xaa | 0xab) {
            let s = bytecode::decode_switch(&m.code, p)?;
            dest.insert(s.default as usize);
            dest.extend(s.cases.iter().map(|(_, v)| *v as usize));
        } else if matches!(op, 0x99..=0xa7 | 0xc6 | 0xc7) {
            let offset = i16::from_be_bytes([m.code[p + 1], m.code[p + 2]]) as i64;
            dest.insert(target(p, offset)?);
            if op != 0xa7 && fall < m.code.len() {
                dest.insert(fall);
            }
        } else if op == 0xc8 {
            let offset = i32::from_be_bytes(m.code[p + 1..p + 5].try_into().unwrap()) as i64;
            dest.insert(target(p, offset)?);
        } else if !matches!(op, 0xac..=0xb1 | 0xbf) && fall < m.code.len() {
            dest.insert(fall);
        }
        for handler in &m.handlers {
            if p >= handler.start && p < handler.end {
                dest.insert(handler.target);
            }
        }
        edges.insert(p, dest);
    }
    let mut pred: BTreeMap<usize, BTreeSet<usize>> = BTreeMap::new();
    for (&p, ds) in &edges {
        for d in ds {
            pred.entry(*d).or_default().insert(p);
        }
    }
    let mut folds = Vec::new();
    // Perfil opt-in equivalente a Java -XX:-FlightRecorder: no elimina la llamada,
    // solo poda la rama inalcanzable cuando el salto consume inmediatamente su resultado.
    if std::env::var("MC_AOT_DISABLE_JFR").as_deref() == Ok("1") {
        for &p in &order {
            if m.code[p] != 0xb8 {
                continue;
            }
            let idx = u16::from_be_bytes([m.code[p + 1], m.code[p + 2]]);
            if method_ref(&m.cp, idx).ok() != Some(("jdk/jfr/FlightRecorder", "isAvailable", "()Z"))
            {
                continue;
            }
            let branch = next[&p];
            if branch >= m.code.len() || !matches!(m.code[branch], 0x99 | 0x9a) {
                continue;
            }
            if pred
                .get(&branch)
                .map_or(true, |s| s.len() != 1 || !s.contains(&p))
            {
                continue;
            }
            let jump = target(
                branch,
                i16::from_be_bytes([m.code[branch + 1], m.code[branch + 2]]) as i64,
            )?;
            folds.push((
                branch,
                if m.code[branch] == 0x99 {
                    jump
                } else {
                    next[&branch]
                },
            ));
        }
    }
    for &p in &order {
        let mut steps = Vec::new();
        let (producer, is_null) = if m.code[p] == 0xb8 {
            let idx = u16::from_be_bytes([m.code[p + 1], m.code[p + 2]]);
            if method_ref(&m.cp, idx).ok()
                != Some((
                    "java/lang/System",
                    "getSecurityManager",
                    "()Ljava/lang/SecurityManager;",
                ))
            {
                continue;
            }
            (p, true)
        } else if matches!(m.code[p], 0x12 | 0x13) {
            let idx = if m.code[p] == 0x12 {
                m.code[p + 1] as u16
            } else {
                u16::from_be_bytes([m.code[p + 1], m.code[p + 2]])
            };
            let target = match m.cp.get(idx as usize) {
                Some(CpEntry::Class(u)) => super::utf(&m.cp, *u).ok(),
                _ => None,
            };
            if !target.is_some_and(|name| !name.starts_with('[') && project_class(name)) {
                continue;
            }
            let call = next[&p];
            if call >= m.code.len() || m.code[call] != 0xb6 {
                continue;
            }
            let idx = u16::from_be_bytes([m.code[call + 1], m.code[call + 2]]);
            if method_ref(&m.cp, idx).ok()
                != Some((
                    "java/lang/Class",
                    "getClassLoader",
                    "()Ljava/lang/ClassLoader;",
                ))
            {
                continue;
            }
            steps.push((call, p));
            (call, false)
        } else {
            continue;
        };
        let p1 = next[&producer];
        if p1 >= m.code.len() {
            continue;
        }
        let p3 = if matches!(m.code[p1], 0xc6 | 0xc7) {
            steps.push((p1, producer));
            p1
        } else {
            let store = m.code[p1];
            if !(0x4b..=0x4e).contains(&store) {
                continue;
            }
            let p2 = next[&p1];
            if p2 >= m.code.len() || m.code[p2] != 0x2a + (store - 0x4b) {
                continue;
            }
            let branch = next[&p2];
            if branch >= m.code.len() || !matches!(m.code[branch], 0xc6 | 0xc7) {
                continue;
            }
            steps.extend([(p1, producer), (p2, p1), (branch, p2)]);
            branch
        };
        if steps.iter().any(|(node, prev)| {
            pred.get(node)
                .map_or(true, |s| s.len() != 1 || !s.contains(prev))
        }) {
            continue;
        }
        let target = target(
            p3,
            i16::from_be_bytes([m.code[p3 + 1], m.code[p3 + 2]]) as i64,
        )?;
        let take = if m.code[p3] == 0xc6 {
            is_null
        } else {
            !is_null
        };
        folds.push((p3, if take { target } else { next[&p3] }));
    }
    if folds.is_empty() {
        return Ok(None);
    }
    for (branch, chosen) in folds {
        // Mantener las aristas de handlers aunque la rama normal sea constante.
        let normal_fall = next[&branch];
        let normal_jump = target(
            branch,
            i16::from_be_bytes([m.code[branch + 1], m.code[branch + 2]]) as i64,
        )?;
        let dest = edges.get_mut(&branch).unwrap();
        dest.remove(&normal_fall);
        dest.remove(&normal_jump);
        dest.insert(chosen);
        for h in &m.handlers {
            if branch >= h.start && branch < h.end {
                dest.insert(h.target);
            }
        }
    }
    let mut reachable = BTreeSet::new();
    let mut queue = VecDeque::from([0]);
    while let Some(p) = queue.pop_front() {
        if !reachable.insert(p) {
            continue;
        }
        if let Some(ds) = edges.get(&p) {
            queue.extend(ds);
        }
    }
    Ok(Some(reachable))
}
#[derive(Clone)]
struct StaticField {
    name: String,
    descriptor: String,
    ty: char,
    initial: String,
    constant_string: Option<Vec<u16>>,
}
#[derive(Clone)]
struct LambdaInfo {
    site: (String, u16),
    interface: String,
    sam_name: String,
    sam_desc: String,
    instantiated: String,
    factory_desc: String,
    impl_kind: u8,
    impl_owner: String,
    impl_name: String,
    impl_desc: String,
}
#[derive(Clone)]
struct InitClass {
    name: String,
    fields: Vec<(usize, StaticField)>,
    clinit: Option<String>,
    instance_fields: Vec<super::metadata::Field>,
    flags: u16,
    inheritable_local: bool,
    enum_class: bool,
    interfaces: Vec<String>,
    init_dependencies: Vec<usize>,
    parent: Option<usize>,
    foreign_exception: bool,
}
fn static_field(f: &super::metadata::Field) -> Result<StaticField> {
    // El modo es estrictamente monohilo: volatile comparte la representación normal.
    let ty = match f.descriptor.as_str() {
        "I" => 'I',
        "J" => 'J',
        "F" => 'F',
        "D" => 'D',
        "Z" => 'Z',
        "B" => 'B',
        "C" => 'C',
        "S" => 'S',
        "Ljava/lang/String;" => 'T',
        "[Ljava/lang/String;" => 't',
        "[Ljava/lang/Object;" | "[Ljava/lang/Class;" => 'a',
        "[I" => 'i',
        "[J" => 'j',
        "[F" => 'f',
        "[D" => 'd',
        "[Z" => 'z',
        "[B" => 'b',
        "[C" => 'c',
        "[S" => 's',
        _ if matches!(super::metadata::field_descriptor(&f.descriptor),Ok(super::metadata::Type::Array(boxed)) if !matches!(*boxed,super::metadata::Type::Int|super::metadata::Type::Long|super::metadata::Type::Float|super::metadata::Type::Double|super::metadata::Type::Byte|super::metadata::Type::Char|super::metadata::Type::Short|super::metadata::Type::Boolean)) => {
            'a'
        }
        _ if project_array(&f.descriptor).is_some() => 'a',
        _ if generic_ref(&f.descriptor) => 'o',
        _ => {
            return Err(format!(
                "campo estático no soportado: {} {}",
                f.name, f.descriptor
            ))
        }
    };
    let mut constant_string = None;
    let initial = if is_ref(ty) {
        match &f.constant {
            None => {}
            Some(super::metadata::ConstantValue::String(units)) if ty == 'T' => {
                constant_string = Some(units.clone())
            }
            _ => return Err(format!("ConstantValue incompatible: {}", f.name)),
        }
        "V::R(None)".to_owned()
    } else {
        match (ty, &f.constant) {
            ('F', None) => "V::F(0.0f32)".to_owned(),
            ('F', Some(super::metadata::ConstantValue::Float(bits))) => {
                format!("V::F(f32::from_bits({bits}u32))")
            }
            ('F', Some(_)) => return Err(format!("ConstantValue incompatible: {}", f.name)),
            ('D', None) => "V::D(0.0f64)".to_owned(),
            ('D', Some(super::metadata::ConstantValue::Double(bits))) => {
                format!("V::D(f64::from_bits({bits}u64))")
            }
            ('D', Some(_)) => return Err(format!("ConstantValue incompatible: {}", f.name)),
            ('J', None) => "V::L(0i64)".to_owned(),
            ('J', Some(super::metadata::ConstantValue::Long(v))) => format!("V::L({v}i64)"),
            ('J', Some(_)) => return Err(format!("ConstantValue incompatible: {}", f.name)),
            (_, None) => "V::I(0i32)".to_owned(),
            (_, Some(super::metadata::ConstantValue::Integer(v))) => {
                format!("V::I({})", super::return_expr(&format!("{v}i32"), ty))
            }
            (_, Some(_)) => return Err(format!("ConstantValue incompatible: {}", f.name)),
        }
    };
    Ok(StaticField {
        name: f.name.clone(),
        descriptor: f.descriptor.clone(),
        ty,
        initial,
        constant_string,
    })
}
struct NumericCompiler<'a> {
    jar: &'a Path,
    class_name: &'a str,
    class_data: &'a [u8],
    active: Vec<String>,
    compiled_methods: std::collections::HashMap<String, String>,
    functions: Vec<String>,
    serial: usize,
    static_fields: Option<Vec<StaticField>>,
    exception_parents: BTreeMap<String, String>,
    multi_classes: Option<Vec<InitClass>>,
    multi_fields: Vec<StaticField>,
    class_literals: BTreeSet<String>,
    uses_service_loader: bool,
    uses_resource_lookup: bool,
    uses_enum_valueof: bool,
    uses_enum_constants: bool,
    interface_calls: Vec<(String, String, String)>,
    virtual_calls: Vec<(String, String, String)>,
    bootstrap_cache: BTreeMap<String, Vec<super::Bootstrap>>,
    lambdas: Vec<LambdaInfo>,
}
impl NumericCompiler<'_> {
    // Solo protege instrucciones que son inalcanzables con la biblioteca exacta
    // y un classpath cerrado sin FrameworkUtil. No elimina isAvailable ni su
    // inicialización; si la rama se ejecuta, el binario aborta explícitamente.
    fn verify_log4j_absent_osgi(&self) -> Result<()> {
        use std::io::Write;
        if std::env::var_os("MC_AOT_CLOSED_CLASSPATH").as_deref() != Some(std::ffi::OsStr::new("1"))
        {
            return Err("Log4j OSGi: requiere MC_AOT_CLOSED_CLASSPATH=1".into());
        }
        if super::classpath::has_class(self.jar, "org/osgi/framework/FrameworkUtil")? {
            return Err("Log4j OSGi: FrameworkUtil presente fuera del perfil".into());
        }
        for (class, expected) in [
            (
                "org/apache/logging/log4j/util/ServiceLoaderUtil",
                "4a1ea71b5c8b7416d62e5b1c46b4a5d35ba7de6f41c56efcb369a448f794f507",
            ),
            (
                "org/apache/logging/log4j/util/OsgiServiceLocator",
                "b3565ae45b7772b1be9e8ecc14fda0b3f6cb76556290245bc846afb86528327e",
            ),
        ] {
            let data = class_from_jar(self.jar, class)?;
            let mut child = std::process::Command::new("sha256sum")
                .stdin(std::process::Stdio::piped())
                .stdout(std::process::Stdio::piped())
                .spawn()
                .map_err(|e| e.to_string())?;
            child
                .stdin
                .take()
                .ok_or("sin stdin sha256sum")?
                .write_all(&data)
                .map_err(|e| e.to_string())?;
            let digest = child.wait_with_output().map_err(|e| e.to_string())?;
            if !digest.status.success()
                || !String::from_utf8_lossy(&digest.stdout).starts_with(&format!("{expected} "))
            {
                return Err(format!("Log4j OSGi: versión no verificada: {class}"));
            }
        }
        Ok(())
    }
    fn verify_log4j_service_spliterator(&self) -> Result<()> {
        use std::io::Write;
        let class = "org/apache/logging/log4j/util/ServiceLoaderUtil$ServiceLoaderSpliterator";
        let data = class_from_jar(self.jar, class)
            .map_err(|_| "Stream.forEach: falta Spliterator Log4j verificado".to_string())?;
        let mut child = std::process::Command::new("sha256sum")
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;
        child
            .stdin
            .take()
            .ok_or("sin stdin sha256sum")?
            .write_all(&data)
            .map_err(|e| e.to_string())?;
        let digest = child.wait_with_output().map_err(|e| e.to_string())?;
        if !digest.status.success()
            || !String::from_utf8_lossy(&digest.stdout)
                .starts_with("f9964a8feaf66c680116797d38c060d9dd40a8e4b595d9378f920f7cf56be97d ")
        {
            return Err("Stream.forEach: Spliterator Log4j versión no verificada".into());
        }
        Ok(())
    }
    fn verify_log4j_status_properties(&self) -> Result<()> {
        use std::io::Write;
        let data = class_from_jar(
            self.jar,
            "org/apache/logging/log4j/status/StatusLogger$PropertiesUtilsDouble",
        )?;
        let mut child = std::process::Command::new("sha256sum")
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;
        child
            .stdin
            .take()
            .ok_or("sin stdin sha256sum")?
            .write_all(&data)
            .map_err(|e| e.to_string())?;
        let digest = child.wait_with_output().map_err(|e| e.to_string())?;
        if !digest.status.success()
            || !String::from_utf8_lossy(&digest.stdout)
                .starts_with("aea79e784c0dcb134efb923065156b4b7ec67ac7fdce3affed24d0fb09795d7c ")
        {
            return Err("PropertiesUtilsDouble: versión de biblioteca no verificada".into());
        }
        super::classpath::require_absent_resource(self.jar, "log4j2.StatusLogger.properties")
    }
    // Resolver el tipo de un catch solo lee su jerarquía; no afirma que sus constructores estén soportados.
    fn resolve_exception_type(&mut self, name: &str) -> Result<()> {
        let mut current = name.to_owned();
        let mut visited = BTreeSet::new();
        while known_exception(&current).is_none() {
            if !project_class(&current) {
                // Para tipos JDK no se dispone del .class: se usa una tabla cerrada
                // del perfil con los padres verificados en JDK 25. Si no está, se rechaza.
                let Some(parent) = jdk_exception_parent(&current) else {
                    return Err(format!("tipo catch no soportado: {name}"));
                };
                if !visited.insert(current.clone()) || visited.len() > 32 {
                    return Err(format!("tipo catch no soportado: {name}"));
                }
                current = parent.to_owned();
                continue;
            }
            if !visited.insert(current.clone()) || visited.len() > 32 {
                return Err(format!("tipo catch no soportado: {name}"));
            }
            let data = if current == self.class_name {
                self.class_data.to_vec()
            } else {
                class_from_jar(self.jar, &current)
                    .map_err(|e| format!("tipo catch no soportado: {name}: {e}"))?
            };
            let meta = super::metadata::parse(&data)?;
            if meta.name != current || meta.flags & 0x0200 != 0 {
                return Err(format!("tipo catch no soportado: {name}"));
            }
            let parent = meta
                .parent
                .ok_or_else(|| format!("tipo catch no es Throwable: {name}"))?;
            self.exception_parents.insert(current, parent.clone());
            current = parent;
        }
        Ok(())
    }
    // Excepciones del bundle sin estado de instancia ni inicializador, con constructores triviales verificados.
    fn validate_exception_class(&mut self, name: &str) -> Result<()> {
        self.resolve_exception_type(name)?;
        let mut current = name.to_owned();
        while known_exception(&current).is_none() {
            let data = if current == self.class_name {
                self.class_data.to_vec()
            } else {
                class_from_jar(self.jar, &current)?
            };
            let meta = super::metadata::parse(&data)?;
            if meta.flags & (0x0200 | 0x0400) != 0
                || !meta.interfaces.is_empty()
                || meta.fields.iter().any(|f| {
                    f.flags & 0x0018 != 0x0018 || f.constant.is_none() || static_field(f).is_err()
                })
                || meta.methods.iter().any(|m| {
                    m.name == "<clinit>"
                        || (m.flags & 0x0008 == 0
                            && matches!(
                                (m.name.as_str(), m.descriptor.as_str()),
                                ("getMessage", "()Ljava/lang/String;")
                                    | ("getLocalizedMessage", "()Ljava/lang/String;")
                                    | ("getCause", "()Ljava/lang/Throwable;")
                                    | ("toString", "()Ljava/lang/String;")
                                    | ("printStackTrace", "(Ljava/io/PrintStream;)V")
                            ))
                })
            {
                return Err(format!(
                    "new de excepción con estado o inicializador no soportado: {current}"
                ));
            }
            current = meta.parent.ok_or("excepción sin padre")?;
        }
        Ok(())
    }
    fn validate_exception_ctor(&mut self, name: &str, desc: &str) -> Result<()> {
        if (name, desc) == ("java/io/UncheckedIOException", "(Ljava/io/IOException;)V") {
            return Ok(());
        }
        if (name, desc)
            == (
                "java/lang/IllegalStateException",
                "(Ljava/lang/String;Ljava/lang/Throwable;)V",
            )
        {
            return Ok(());
        }
        if !matches!(
            desc,
            "()V"
                | "(Ljava/lang/String;)V"
                | "(Ljava/lang/Throwable;)V"
                | "(Ljava/lang/String;Ljava/lang/Throwable;)V"
        ) {
            return Err(format!(
                "constructor de excepción no soportado: {name}{desc}"
            ));
        }
        self.validate_exception_class(name)?;
        let mut current = name.to_owned();
        while known_exception(&current).is_none() {
            let data = if current == self.class_name {
                self.class_data.to_vec()
            } else {
                class_from_jar(self.jar, &current)?
            };
            let meta = super::metadata::parse(&data)?;
            let parent = meta.parent.ok_or("excepción sin padre")?;
            let ctor = super::find_instance_method(&data, "<init>", desc)?;
            let code = &ctor.code;
            let prefix = match desc {
                "()V" => &[0x2au8][..],
                "(Ljava/lang/String;Ljava/lang/Throwable;)V" => &[0x2au8, 0x2b, 0x2c][..],
                _ => &[0x2au8, 0x2b][..],
            };
            let at = prefix.len();
            if code.len() != at + 4
                || !code.starts_with(prefix)
                || code[at] != 0xb7
                || code[at + 3] != 0xb1
            {
                return Err(format!(
                    "constructor de excepción no trivial: {current}{desc}"
                ));
            }
            let index = u16::from_be_bytes([code[at + 1], code[at + 2]]);
            if method_ref(&ctor.cp, index)? != (parent.as_str(), "<init>", desc) {
                return Err(format!(
                    "constructor de excepción no trivial: {current}{desc}"
                ));
            }
            current = parent;
        }
        if matches!(
            desc,
            "(Ljava/lang/Throwable;)V"
                | "(Ljava/io/IOException;)V"
                | "(Ljava/lang/String;Ljava/lang/Throwable;)V"
        ) && !matches!(
            current.as_str(),
            "java/lang/Throwable"
                | "java/lang/Exception"
                | "java/lang/RuntimeException"
                | "java/lang/IllegalStateException"
                | "java/lang/IllegalArgumentException"
                | "java/util/concurrent/CancellationException"
                | "java/lang/MatchException"
                | "java/lang/InternalError"
        ) {
            return Err(format!(
                "constructor Throwable JDK no verificado: {current}{desc}"
            ));
        }
        Ok(())
    }
    fn exception_parent_source(&self) -> String {
        let arms = self
            .exception_parents
            .iter()
            .map(|(class, parent)| format!("{class:?}=>Some({parent:?}),"))
            .collect::<Vec<_>>()
            .join("");
        format!("fn user_exception_parent(name:&str)->Option<&'static str> {{match name {{{arms}_=>None}}}}")
    }
    // Orden JVM: padres antes que hijos, solo interfaces que declaran defaults.
    fn default_interface_order(&self, interfaces: &[String]) -> Result<Vec<String>> {
        fn visit(
            jar: &Path,
            name: &str,
            done: &mut BTreeSet<String>,
            active: &mut BTreeSet<String>,
            out: &mut Vec<String>,
        ) -> Result<()> {
            if done.contains(name) {
                return Ok(());
            }
            if !active.insert(name.to_owned()) {
                return Err(format!("ciclo de interfaces: {name}"));
            }
            if jdk_function_interface(name)
                || matches!(
                    name,
                    "java/lang/Cloneable"
                        | "java/lang/CharSequence"
                        | "java/io/Serializable"
                        | "java/util/Map"
                        | "java/lang/Comparable"
                        | "java/util/Collection"
                        | "java/util/Comparator"
                        | "java/util/Spliterator"
                        | "java/util/List"
                        | "java/util/Set"
                        | "java/util/Map$Entry"
                        | "java/util/SequencedSet"
                        | "java/util/SequencedCollection"
                        | "java/util/SequencedMap"
                        | "java/util/SortedSet"
                        | "java/util/NavigableSet"
                        | "java/util/SortedMap"
                        | "java/util/NavigableMap"
                        | "java/lang/Iterable"
                        | "java/util/RandomAccess"
                        | "java/io/Closeable"
                        | "java/io/Externalizable"
                        | "java/util/EventListener"
                        | "java/lang/AutoCloseable"
                        | "java/lang/reflect/Type"
                        | "java/lang/reflect/ParameterizedType"
                        | "java/lang/reflect/GenericArrayType"
                        | "java/lang/reflect/WildcardType"
                        | "java/lang/reflect/TypeVariable"
                        | "java/lang/reflect/TypeVariable$GenericDeclaration"
                        | "java/lang/reflect/GenericDeclaration"
                        | "java/lang/reflect/AnnotatedType"
                        | "java/lang/reflect/AnnotatedElement"
                        | "java/util/concurrent/Executor"
                        | "java/util/concurrent/ExecutorService"
                        | "java/util/concurrent/ScheduledExecutorService"
                        | "java/util/concurrent/Future"
                        | "java/util/concurrent/ScheduledFuture"
                        | "java/util/concurrent/RejectedExecutionHandler"
                        | "java/util/concurrent/RunnableFuture"
                        | "java/util/concurrent/RunnableScheduledFuture"
                        | "java/util/concurrent/Callable"
                        | "java/util/concurrent/CompletionStage"
                        | "java/nio/file/PathMatcher"
                        | "java/util/function/DoubleUnaryOperator"
                )
            {
                active.remove(name);
                done.insert(name.to_owned());
                return Ok(());
            }
            // Clase abstracta guava (no interfaz): solo se acepta como receptor
            // abstracto de `load`, implementada por clases proyecto precompiladas.
            if name == "com/google/common/cache/CacheLoader" {
                let data = class_from_jar(jar, name)?;
                let meta = super::metadata::parse(&data)?;
                if meta.name != name
                    || meta.flags & 0x0400 == 0
                    || meta.flags & 0x0200 != 0
                    || meta.parent.as_deref() != Some("java/lang/Object")
                {
                    return Err(format!("clase CacheLoader inesperada: {name}"));
                }
                active.remove(name);
                done.insert(name.to_owned());
                return Ok(());
            }
            if !project_class(name) {
                return Err(format!("interfaz JDK no inspeccionada: {name}"));
            }
            let data = class_from_jar(jar, name)?;
            let meta = super::metadata::parse(&data)?;
            if meta.name != name
                || meta.flags & 0x0200 == 0
                || meta.parent.as_deref() != Some("java/lang/Object")
            {
                return Err(format!("interfaz inválida: {name}"));
            }
            for parent in &meta.interfaces {
                visit(jar, parent, done, active, out)?;
            }
            if meta
                .methods
                .iter()
                .any(|m| m.flags & (0x0008 | 0x0400) == 0 && !m.name.starts_with('<'))
            {
                out.push(name.to_owned());
            }
            active.remove(name);
            done.insert(name.to_owned());
            Ok(())
        }
        let mut out = Vec::new();
        let mut done = BTreeSet::new();
        let mut active = BTreeSet::new();
        for name in interfaces {
            visit(self.jar, name, &mut done, &mut active, &mut out)?;
        }
        Ok(out)
    }
    // Interfaces ya verificadas al registrar la clase; no se inicializan aquí.
    fn interface_closure(&self, names: &[String]) -> Result<BTreeSet<String>> {
        let mut out = BTreeSet::new();
        let mut todo = names.to_vec();
        while let Some(name) = todo.pop() {
            if !out.insert(name.clone()) {
                continue;
            }
            if project_class(&name) {
                let data = class_from_jar(self.jar, &name)?;
                let meta = super::metadata::parse(&data)?;
                todo.extend(meta.interfaces);
            } else {
                match name.as_str() {
                    "java/util/List" | "java/util/Set" => todo.push("java/util/Collection".into()),
                    "java/util/SequencedSet" => todo.push("java/util/Set".into()),
                    "java/util/SequencedCollection" => todo.push("java/util/Collection".into()),
                    "java/util/SequencedMap" => todo.push("java/util/Map".into()),
                    "java/util/SortedSet" | "java/util/NavigableSet" => {
                        todo.push("java/util/SequencedSet".into())
                    }
                    "java/util/SortedMap" | "java/util/NavigableMap" => {
                        todo.push("java/util/SequencedMap".into())
                    }
                    "java/util/Collection" => todo.push("java/lang/Iterable".into()),
                    "java/io/Closeable" => todo.push("java/lang/AutoCloseable".into()),
                    "java/io/Externalizable" => todo.push("java/io/Serializable".into()),
                    "java/util/function/BinaryOperator" => {
                        todo.push("java/util/function/BiFunction".into())
                    }
                    "java/lang/reflect/ParameterizedType"
                    | "java/lang/reflect/GenericArrayType"
                    | "java/lang/reflect/WildcardType"
                    | "java/lang/reflect/TypeVariable" => todo.push("java/lang/reflect/Type".into()),
                    "java/lang/reflect/AnnotatedType" => {
                        todo.push("java/lang/reflect/AnnotatedElement".into())
                    }

                    _ => {}
                }
            }
        }
        Ok(out)
    }
    fn verify_cast_interface(&self, name: &str) -> Result<()> {
        fn visit(
            jar: &Path,
            name: &str,
            done: &mut BTreeSet<String>,
            active: &mut BTreeSet<String>,
        ) -> Result<()> {
            if done.contains(name) {
                return Ok(());
            }
            if !active.insert(name.to_owned()) {
                return Err(format!("ciclo de interfaces: {name}"));
            }
            if jdk_function_interface(name)
                || matches!(
                    name,
                    "java/lang/Cloneable"
                        | "java/lang/CharSequence"
                        | "java/io/Serializable"
                        | "java/util/Map"
                        | "java/lang/Comparable"
                        | "java/util/Collection"
                        | "java/util/Comparator"
                        | "java/util/Spliterator"
                        | "java/util/List"
                        | "java/util/Set"
                        | "java/util/Map$Entry"
                        | "java/util/SequencedSet"
                        | "java/util/SequencedCollection"
                        | "java/util/SequencedMap"
                        | "java/util/SortedSet"
                        | "java/util/NavigableSet"
                        | "java/util/SortedMap"
                        | "java/util/NavigableMap"
                        | "java/lang/Iterable"
                        | "java/util/RandomAccess"
                        | "java/io/Closeable"
                        | "java/io/Externalizable"
                        | "java/util/EventListener"
                        | "java/lang/AutoCloseable"
                        | "java/lang/reflect/Type"
                        | "java/lang/reflect/ParameterizedType"
                        | "java/lang/reflect/GenericArrayType"
                        | "java/lang/reflect/WildcardType"
                        | "java/lang/reflect/TypeVariable"
                        | "java/lang/reflect/TypeVariable$GenericDeclaration"
                        | "java/lang/reflect/GenericDeclaration"
                        | "java/lang/reflect/AnnotatedType"
                        | "java/lang/reflect/AnnotatedElement"
                        | "java/util/concurrent/Executor"
                        | "java/util/concurrent/ExecutorService"
                        | "java/util/concurrent/ScheduledExecutorService"
                        | "java/util/concurrent/Future"
                        | "java/util/concurrent/ScheduledFuture"
                        | "java/util/concurrent/RejectedExecutionHandler"
                        | "java/util/concurrent/RunnableFuture"
                        | "java/util/concurrent/RunnableScheduledFuture"
                        | "java/util/concurrent/Callable"
                        | "java/util/concurrent/CompletionStage"
                        | "java/nio/file/PathMatcher"
                        | "java/util/function/DoubleUnaryOperator"
                )
            {
                active.remove(name);
                done.insert(name.to_owned());
                return Ok(());
            }
            // Clase abstracta guava (no interfaz): solo se acepta como receptor
            // abstracto de `load`, implementada por clases proyecto precompiladas.
            if name == "com/google/common/cache/CacheLoader" {
                let data = class_from_jar(jar, name)?;
                let meta = super::metadata::parse(&data)?;
                if meta.name != name
                    || meta.flags & 0x0400 == 0
                    || meta.flags & 0x0200 != 0
                    || meta.parent.as_deref() != Some("java/lang/Object")
                {
                    return Err(format!("clase CacheLoader inesperada: {name}"));
                }
                for p in &meta.interfaces { visit(jar, p, done, active)?; }
                active.remove(name);
                done.insert(name.to_owned());
                return Ok(());
            }
            if !project_class(name) {
                return Err(format!("interfaz JDK no inspeccionada: {name}"));
            }
            let data = class_from_jar(jar, name)?;
            let meta = super::metadata::parse(&data)?;
            if meta.name != name
                || meta.flags & 0x0200 == 0
                || meta.parent.as_deref() != Some("java/lang/Object")
            {
                return Err(format!("interfaz inválida: {name}"));
            }
            for parent in &meta.interfaces {
                visit(jar, parent, done, active)?;
            }
            active.remove(name);
            done.insert(name.to_owned());
            Ok(())
        }
        visit(self.jar, name, &mut BTreeSet::new(), &mut BTreeSet::new())
    }
    fn verify_project_cast_target(&mut self, name: &str) -> Result<()> {
        let data = if name == self.class_name {
            self.class_data.to_vec()
        } else {
            class_from_jar(self.jar, name)?
        };
        let meta = super::metadata::parse(&data)?;
        if meta.name != name {
            return Err(format!("tipo de cast inválido: {name}"));
        }
        if meta.flags & 0x0200 != 0 {
            self.verify_cast_interface(name)?;
        } else {
            // checkcast no inicializa la clase de destino. Se comprueba la cadena
            // pero no se crean objetos de sus superclases no soportadas.
            let mut current = name.to_owned();
            let mut seen = BTreeSet::new();
            loop {
                if !seen.insert(current.clone()) {
                    return Err(format!("ciclo de superclases: {current}"));
                }
                let data = class_from_jar(self.jar, &current)?;
                let ty = super::metadata::parse(&data)?;
                if ty.name != current || ty.flags & 0x0200 != 0 {
                    return Err(format!("clase de cast inválida: {current}"));
                }
                let parent = ty.parent.ok_or("clase de cast sin superclase")?;
                if matches!(
                    parent.as_str(),
                    "java/lang/Object"
                        | "java/lang/Enum"
                        | "java/lang/InheritableThreadLocal"
                        | "java/lang/SecurityManager"
                        | "java/lang/Exception"
                        | "java/lang/RuntimeException"
                        | "java/util/concurrent/CancellationException"
                        | "java/util/concurrent/AbstractExecutorService"
                        | "java/lang/Error"
                        | "java/lang/Throwable"
                        | "java/lang/Record"
                        | "java/util/AbstractCollection"
                        | "java/util/AbstractMap"
                        | "java/util/AbstractSet"
                        | "java/io/PrintStream"
                ) {
                    break;
                }
                if !project_class(&parent) {
                    return Err(format!("superclase JDK de cast no inspeccionada: {parent}"));
                }
                current = parent;
            }
        }
        Ok(())
    }
    fn ensure_multi_class(&mut self, class: &str) -> Result<usize> {
        let classes = self.multi_classes.as_ref().ok_or("modo multi no activo")?;
        if let Some(i) = classes.iter().position(|c| c.name == class) {
            return Ok(i);
        }
        let class_limit=match std::env::var("MC_AOT_MAX_STATIC_CLASSES") {
            Ok(s)=>s.parse::<usize>().ok().filter(|v|(1..=4096).contains(v)).ok_or("MC_AOT_MAX_STATIC_CLASSES debe estar entre 1 y 4096")?,
            Err(std::env::VarError::NotPresent)=>256,
            Err(_)=>return Err("MC_AOT_MAX_STATIC_CLASSES inválido".into()),
        };
        if classes.len() >= class_limit {
            return Err(format!("límite experimental de clases estáticas ({class_limit}; MC_AOT_MAX_STATIC_CLASSES)"));
        }
        if !project_class(class) {
            return Err(format!("clase estática externa no soportada: {class}"));
        }
        let data = if class == self.class_name {
            self.class_data.to_vec()
        } else {
            class_from_jar(self.jar, class)?
        };
        let meta = super::metadata::parse(&data)?;
        let inheritable_local = meta.parent.as_deref() == Some("java/lang/InheritableThreadLocal");
        let security_manager = meta.parent.as_deref() == Some("java/lang/SecurityManager");
        let record = meta.parent.as_deref() == Some("java/lang/Record");
        // commons-lang3 Fraction y similares: aritmética entera pura sobre Number.
        let number_class = meta.parent.as_deref() == Some("java/lang/Number")
            && !meta.flags & 0x0400 == 0x0400;
        let abstract_collection = meta.parent.as_deref() == Some("java/util/AbstractCollection");
        let abstract_map = meta.parent.as_deref() == Some("java/util/AbstractMap");
        let abstract_set = meta.parent.as_deref() == Some("java/util/AbstractSet");
        let print_stream = meta.parent.as_deref() == Some("java/io/PrintStream");
        let abstract_list = meta.parent.as_deref() == Some("java/util/AbstractList");
        let abstract_sequential_list =
            meta.parent.as_deref() == Some("java/util/AbstractSequentialList");
        // netty MultithreadEventExecutorGroup: ejecutor abstracto JDK; herencia transparente.
        let abstract_executor_service =
            meta.parent.as_deref() == Some("java/util/concurrent/AbstractExecutorService");
        let abstract_spliterator =
            meta.parent.as_deref() == Some("java/util/Spliterators$AbstractSpliterator");
        if abstract_spliterator
            && (meta.flags & 0x10 == 0
                || meta.methods.iter().any(|m| {
                    matches!(
                        m.name.as_str(),
                        "estimateSize"
                            | "characteristics"
                            | "getExactSizeIfKnown"
                            | "hasCharacteristics"
                            | "getComparator"
                            | "trySplit"
                            | "forEachRemaining"
                    )
                }))
        {
            return Err(format!(
                "AbstractSpliterator: subclase u override no soportado: {class}"
            ));
        }
        let foreign_exception = matches!(
            meta.parent.as_deref(),
            Some(
                "java/lang/Exception"
                    | "java/lang/RuntimeException"
                    | "java/lang/Error"
                    | "java/lang/Throwable"
                    | "java/util/concurrent/CancellationException"
            )
        );
        // Enum directo; las subclases específicas heredan estado del enum base.
        let enum_class =
            meta.parent.as_deref() == Some("java/lang/Enum") && meta.flags & 0x4000 != 0;
        let project_parent = meta.parent.as_deref().filter(|p| project_class(p));
        if meta.name != class
            || (meta.parent.as_deref() != Some("java/lang/Object")
                && !inheritable_local
                && !enum_class
                && !security_manager
                && !record
                && !abstract_collection
                && !abstract_map
                && !abstract_set
                && !print_stream
                && !abstract_list
                && !abstract_sequential_list
                && !abstract_executor_service
                && !abstract_spliterator
                && !foreign_exception
                && !number_class
                && project_parent.is_none())
        {
            return Err(format!("superclase JDK no soportada: {class}"));
        }
        if project_parent.is_some() {
            self.verify_project_cast_target(class)?;
        }
        if inheritable_local
            && meta
                .methods
                .iter()
                .any(|m| matches!(m.name.as_str(), "initialValue" | "get" | "set" | "remove"))
        {
            return Err(format!("override ThreadLocal no soportado: {class}"));
        }
        let default_order = if meta.flags & 0x0200 != 0 {
            self.verify_cast_interface(class)?;
            Vec::new()
        } else {
            self.default_interface_order(&meta.interfaces)?
        };
        let mut fields = Vec::new();
        for f in meta.fields.iter().filter(|f| f.flags & 0x0008 != 0) {
            let field = static_field(f)?;
            let slot = self.multi_fields.len();
            self.multi_fields.push(field.clone());
            fields.push((slot, field));
        }
        let id = self.multi_classes.as_ref().unwrap().len();
        self.multi_classes.as_mut().unwrap().push(InitClass {
            name: class.to_owned(),
            fields,
            clinit: None,
            instance_fields: meta
                .fields
                .iter()
                .filter(|f| f.flags & 0x0008 == 0)
                .cloned()
                .collect(),
            flags: meta.flags,
            inheritable_local,
            enum_class,
            interfaces: meta.interfaces.clone(),
            init_dependencies: Vec::new(),
            parent: None,
            foreign_exception,
        });
        let mut dependencies = Vec::new();
        if let Some(parent) = project_parent {
            let parent_id = self.ensure_multi_class(parent)?;
            let flags = self.multi_classes.as_ref().unwrap()[parent_id].flags;
            if flags & (0x0010 | 0x0200) != 0 {
                return Err(format!("superclase final o interfaz: {parent}"));
            }
            let inherited_exception =
                self.multi_classes.as_ref().unwrap()[parent_id].foreign_exception;
            let inherited_enum = self.multi_classes.as_ref().unwrap()[parent_id].enum_class;
            self.multi_classes.as_mut().unwrap()[id].parent = Some(parent_id);
            self.multi_classes.as_mut().unwrap()[id].foreign_exception |= inherited_exception;
            self.multi_classes.as_mut().unwrap()[id].enum_class |= inherited_enum;
            dependencies.push(parent_id);
        }
        for interface in default_order {
            dependencies.push(self.ensure_multi_class(&interface)?);
        }
        self.multi_classes.as_mut().unwrap()[id].init_dependencies = dependencies;
        if meta
            .methods
            .iter()
            .any(|m| m.name == "<clinit>" && m.descriptor == "()V")
        {
            let init = self.compile(class, "<clinit>", "()V")?;
            self.multi_classes.as_mut().unwrap()[id].clinit = Some(init);
        }
        Ok(id)
    }
    fn resolve_static_field(
        &mut self,
        class: &str,
        name: &str,
        desc: &str,
    ) -> Result<(usize, usize, StaticField)> {
        fn visit(
            compiler: &mut NumericCompiler<'_>,
            class: &str,
            name: &str,
            desc: &str,
            seen: &mut BTreeSet<String>,
        ) -> Result<Option<(usize, usize, StaticField)>> {
            if !seen.insert(class.to_owned()) {
                return Ok(None);
            }
            let id = compiler.ensure_multi_class(class)?;
            let c = compiler.multi_classes.as_ref().unwrap()[id].clone();
            if let Some((slot, field)) = c
                .fields
                .iter()
                .find(|(_, f)| f.name == name && f.descriptor == desc)
            {
                return Ok(Some((id, *slot, field.clone())));
            }
            for iface in &c.interfaces {
                if !project_class(iface) {
                    continue;
                }
                if let Some(f) = visit(compiler, iface, name, desc, seen)? {
                    return Ok(Some(f));
                }
            }
            if let Some(parent) = c.parent {
                let parent_name = compiler.multi_classes.as_ref().unwrap()[parent]
                    .name
                    .clone();
                return visit(compiler, &parent_name, name, desc, seen);
            }
            Ok(None)
        }
        visit(self, class, name, desc, &mut BTreeSet::new())?
            .ok_or_else(|| format!("campo estático no declarado: {class}.{name}{desc}"))
    }
    fn multi_init_source(&self) -> String {
        self.multi_classes.as_ref().unwrap().iter().enumerate().map(|(i,c)|{
            let constants=c.fields.iter().filter_map(|(slot,f)|f.constant_string.as_ref().map(|units| {
                let list=units.iter().map(|v|format!("{v}u16")).collect::<Vec<_>>().join(",");
                format!("let s=string_literal(heap,&[{list}]);heap.fields[{slot}]=V::R(Some(s));")
            })).collect::<String>();
            let dependencies=c.init_dependencies.iter().map(|id|format!("init_class_{id}(heap);" )).collect::<String>();
            let call=format!("{dependencies}{}",c.clinit.as_ref().map(|f|format!("{f}(heap);" )).unwrap_or_default());
            format!("fn init_class_{i}(heap:&mut Heap) {{match heap.init_states[{i}] {{1|2=>return,3=>raise(\"NoClassDefFoundError\",\"\"),0=>(),_=>panic!(\"estado de inicialización inválido\")}} heap.init_states[{i}]=1; {constants} let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {{ {call} }})); match result {{Ok(())=>heap.init_states[{i}]=2,Err(payload)=>{{heap.init_states[{i}]=3;if let Some(e)=payload.downcast_ref::<JException>() {{if !exception_matches(e.kind,\"java/lang/Error\") {{raise(\"ExceptionInInitializerError\",\"\");}}}}std::panic::resume_unwind(payload);}}}}}}\n")
        }).collect()
    }
    fn ensure_class_literal(&mut self, class: &str) -> Result<()> {
        let data = if class == self.class_name {
            self.class_data.to_vec()
        } else {
            class_from_jar(self.jar, class)?
        };
        let meta = super::metadata::parse(&data)?;
        if meta.name != class {
            return Err(format!("Class con nombre incompatible: {class}"));
        }
        if meta.flags & 0x0200 != 0 {
            if meta.parent.as_deref() != Some("java/lang/Object") {
                return Err(format!("superclase de interfaz inválida: {class}"));
            }
            self.verify_cast_interface(class)?;
        } else {
            self.ensure_multi_class(class)?;
        }
        Ok(())
    }
    fn instance_layout(&mut self, class: &str) -> Result<Vec<StaticField>> {
        let id = self.ensure_multi_class(class)?;
        if self.multi_classes.as_ref().unwrap()[id].foreign_exception {
            return Err(format!(
                "instancia de excepción externa no soportada: {class}"
            ));
        }
        let parent = self.multi_classes.as_ref().unwrap()[id].parent;
        let mut out = if let Some(parent) = parent {
            let name = self.multi_classes.as_ref().unwrap()[parent].name.clone();
            self.instance_layout(&name)?
        } else {
            Vec::new()
        };
        let fields = self.multi_classes.as_ref().unwrap()[id]
            .instance_fields
            .clone();
        for mut field in fields {
            field.constant = None;
            out.push(static_field(&field)?);
        }
        Ok(out)
    }
    fn resolve_instance_field(
        &mut self,
        class: &str,
        name: &str,
        desc: &str,
    ) -> Result<(String, usize, StaticField)> {
        let id = self.ensure_multi_class(class)?;
        let info = self.multi_classes.as_ref().unwrap()[id].clone();
        if let Some((index, field)) = info
            .instance_fields
            .iter()
            .enumerate()
            .find(|(_, f)| f.name == name && f.descriptor == desc)
        {
            let prefix = if let Some(p) = info.parent {
                let n = self.multi_classes.as_ref().unwrap()[p].name.clone();
                self.instance_layout(&n)?.len()
            } else {
                0
            };
            let mut field = field.clone();
            field.constant = None;
            return Ok((class.to_owned(), prefix + index, static_field(&field)?));
        }
        // Las interfaces contienen campos estáticos; no confundirlos con campos de instancia.
        fn interface_has_field(
            jar: &Path,
            iface: &str,
            name: &str,
            desc: &str,
            seen: &mut BTreeSet<String>,
        ) -> Result<bool> {
            if !project_class(iface) || !seen.insert(iface.to_owned()) {
                return Ok(false);
            }
            let data = class_from_jar(jar, iface)?;
            let meta = super::metadata::parse(&data)?;
            if meta
                .fields
                .iter()
                .any(|f| f.name == name && f.descriptor == desc)
            {
                return Ok(true);
            }
            for parent in &meta.interfaces {
                if interface_has_field(jar, parent, name, desc, seen)? {
                    return Ok(true);
                }
            }
            Ok(false)
        }
        for iface in &info.interfaces {
            if interface_has_field(self.jar, iface, name, desc, &mut BTreeSet::new())? {
                return Err(format!(
                    "getfield resuelve a campo de interfaz estático: {iface}.{name}"
                ));
            }
        }
        if let Some(p) = info.parent {
            let n = self.multi_classes.as_ref().unwrap()[p].name.clone();
            return self.resolve_instance_field(&n, name, desc);
        }
        Err(format!(
            "campo de instancia no declarado: {class}.{name}{desc}"
        ))
    }
    fn is_project_subclass(&self, class: &str, ancestor: &str) -> bool {
        let classes = self.multi_classes.as_ref().unwrap();
        let mut id = classes.iter().position(|c| c.name == class);
        while let Some(i) = id {
            if classes[i].name == ancestor {
                return true;
            }
            id = classes[i].parent;
        }
        false
    }
    fn same_package_chain(&self, class: &str, ancestor: &str) -> bool {
        let classes = self.multi_classes.as_ref().unwrap();
        let package = ancestor.rsplit_once('/').map(|x| x.0);
        let mut id = classes.iter().position(|c| c.name == class);
        while let Some(i) = id {
            if classes[i].name.rsplit_once('/').map(|x| x.0) != package {
                return false;
            }
            if classes[i].name == ancestor {
                return true;
            }
            id = classes[i].parent;
        }
        false
    }
    fn class_interfaces(&self, class: &str) -> Result<BTreeSet<String>> {
        let classes = self.multi_classes.as_ref().unwrap();
        let mut id = classes.iter().position(|c| c.name == class);
        let mut out = BTreeSet::new();
        while let Some(i) = id {
            out.extend(self.interface_closure(&classes[i].interfaces)?);
            let data = class_from_jar(self.jar, &classes[i].name)?;
            let meta = super::metadata::parse(&data)?;
            if meta.parent.as_deref() == Some("java/util/AbstractCollection") {
                out.insert("java/util/Collection".into());
                out.insert("java/lang/Iterable".into());
            }
            if meta.parent.as_deref() == Some("java/util/Spliterators$AbstractSpliterator") {
                out.insert("java/util/Spliterator".into());
            }
            id = classes[i].parent;
        }
        Ok(out)
    }
    fn virtual_implementation(
        &self,
        class: &str,
        method: &str,
        desc: &str,
    ) -> Result<Option<String>> {
        let classes = self.multi_classes.as_ref().unwrap();
        let mut id = classes.iter().position(|c| c.name == class);
        while let Some(i) = id {
            let c = &classes[i];
            let data = class_from_jar(self.jar, &c.name)?;
            let meta = super::metadata::parse(&data)?;
            if let Some(m) = meta.methods.iter().find(|m| {
                m.name == method && m.descriptor == desc && m.flags & (0x0002 | 0x0008) == 0
            }) {
                if m.flags & 0x0400 != 0 {
                    return Ok(None);
                }
                return Ok(Some(c.name.clone()));
            }
            id = c.parent;
        }
        Ok(None)
    }
    // Las declaraciones public/protected permiten overrides entre paquetes;
    // package-private conserva la guarda por las reglas JVM más sutiles.
    fn cross_package_public_or_protected(
        &self,
        class: &str,
        method: &str,
        desc: &str,
    ) -> Result<bool> {
        let classes = self.multi_classes.as_ref().unwrap();
        let mut id = classes.iter().position(|c| c.name == class);
        while let Some(i) = id {
            let c = &classes[i];
            let data = class_from_jar(self.jar, &c.name)?;
            let meta = super::metadata::parse(&data)?;
            if let Some(m) = meta
                .methods
                .iter()
                .find(|m| m.name == method && m.descriptor == desc && m.flags & 0x0008 == 0)
            {
                return Ok(m.flags & 0x0005 != 0 && m.flags & 0x0002 == 0);
            }
            id = c.parent;
        }
        Ok(false)
    }
    // Registra "java/lang/Object","hashCode","()I" en el despacho virtual sin pasar
    // por ensure_multi_class (Object es JDK): los brazos se generan por subclase
    // proyecto que sobrescribe hashCode; sin override no hay brazo (aborta).
    fn register_object_hashcode(&mut self) -> usize {
        let key = (
            "java/lang/Object".to_owned(),
            "hashCode".to_owned(),
            "()I".to_owned(),
        );
        if let Some(n) = self.virtual_calls.iter().position(|k| *k == key) {
            return n;
        }
        let n = self.virtual_calls.len();
        self.virtual_calls.push(key);
        n
    }
    fn virtual_call(&mut self, owner: &str, method: &str, desc: &str) -> Result<String> {
        self.ensure_multi_class(owner)?;
        let data = class_from_jar(self.jar, owner)?;
        let meta = super::metadata::parse(&data)?;
        if meta
            .methods
            .iter()
            .any(|m| m.name == method && m.descriptor == desc && m.flags & 0x0002 != 0)
        {
            return self.instance_call(owner, method, desc);
        }
        let sig = signature_ext(desc, true)?;
        let key = (owner.to_owned(), method.to_owned(), desc.to_owned());
        let id = if let Some(n) = self.virtual_calls.iter().position(|k| *k == key) {
            n
        } else {
            let n = self.virtual_calls.len();
            self.virtual_calls.push(key);
            n
        };
        let mut pre = String::new();
        for (i, t) in sig.args.iter().enumerate().rev() {
            pre.push_str(&format!("let x{i}={}(&mut stack);", pop(*t)));
        }
        pre.push_str("let r=pop_r(&mut stack);");
        let args = (0..sig.args.len())
            .map(|i| format!(",x{i}"))
            .collect::<String>();
        let call = format!("virtual_dispatch_{id}(heap,r{args})");
        if sig.ret == 'V' {
            Ok(format!("{pre}{call};"))
        } else {
            Ok(format!("{pre}stack.push(V::{}({call}));", variant(sig.ret)))
        }
    }
    fn compile_instance(&mut self, class: &str, method: &str, desc: &str) -> Result<String> {
        if self.multi_classes.is_none() {
            return Err("métodos de instancia solo en multi-static-demo".into());
        }
        let id = self.ensure_multi_class(class)?;
        if self.multi_classes.as_ref().unwrap()[id].foreign_exception {
            return Err(format!("método de excepción externa no soportado: {class}"));
        }
        let sig = signature_ext(desc, true)?;
        let key = format!("{class}.{method}{desc}");
        let cache_key = format!("instance:{key}");
        if let Some(f) = self.compiled_methods.get(&cache_key) {
            return Ok(f.clone());
        }
        if self.active.len() >= 32 {
            return Err("profundidad de llamadas mayor a 32".into());
        }
        let data = if class == self.class_name {
            self.class_data.to_vec()
        } else {
            class_from_jar(self.jar, class)?
        };
        let m = super::find_method_inner(&data, method, desc, true, false, true)
            .map_err(|e| format!("{e}\n  al obtener {key}"))?;
        let rust_name = format!("numeric_{}", self.serial);
        self.serial += 1;
        self.compiled_methods.insert(cache_key, rust_name.clone());
        self.active.push(key.clone());
        let pump = if class == "net/minecraft/server/MinecraftServer" && method == "tickServer" && desc == "(Ljava/util/function/BooleanSupplier;)V" {Some("scheduled_pool_poll(heap);\n    ")} else {None};
        let out = self.lower(&m, &sig, &rust_name, class, None, true, pump);
        self.active.pop();
        self.functions
            .push(out.map_err(|e| format!("{e}\n  al compilar {key}"))?);
        Ok(rust_name)
    }
    fn threadlocal_get_call(&mut self) -> Result<String> {
        let owner = "java/util/function/Supplier";
        let method = "get";
        let desc = "()Ljava/lang/Object;";
        self.interface_call(owner, method, desc)?;
        let id = self
            .interface_calls
            .iter()
            .position(|x| x.0 == owner && x.1 == method && x.2 == desc)
            .ok_or("Supplier.get no registrado")?;
        Ok(format!("let r=pop_r(&mut stack);stack.push(V::R(threadlocal_get(heap,r,interface_dispatch_{id})));"))
    }
    fn map_compute_if_absent(&mut self) -> Result<String> {
        let owner = "java/util/function/Function";
        let method = "apply";
        let desc = "(Ljava/lang/Object;)Ljava/lang/Object;";
        self.interface_call(owner, method, desc)?;
        let id = self
            .interface_calls
            .iter()
            .position(|x| x.0 == owner && x.1 == method && x.2 == desc)
            .ok_or("Function.apply no registrada")?;
        Ok(format!("let fun=pop_r(&mut stack);let key=pop_r(&mut stack);let map=pop_r(&mut stack);let result=map_compute(heap,map,key,fun,interface_dispatch_{id});stack.push(V::R(result));"))
    }
    fn interface_call(&mut self, owner: &str, method: &str, desc: &str) -> Result<String> {
        // Los defaults no se despachan: solo implementaciones directas precompiladas;
        // cualquier receptor sin implementación directa termina en guarda explícita.
        self.verify_cast_interface(owner)?;
        if !project_class(owner)
            && !jdk_function_method(owner, method, desc)
            && (owner, method, desc)
                != (
                    "java/util/Spliterator",
                    "tryAdvance",
                    "(Ljava/util/function/Consumer;)Z",
                )
        {
            return Err(format!(
                "invokeinterface JDK no soportado: {owner}.{method}{desc}"
            ));
        }
        let sig = signature_ext(desc, true)?;
        let key = (owner.to_owned(), method.to_owned(), desc.to_owned());
        let id = if let Some(i) = self.interface_calls.iter().position(|k| *k == key) {
            i
        } else {
            let n = self.interface_calls.len();
            self.interface_calls.push(key);
            n
        };
        let mut pre = String::new();
        for (i, t) in sig.args.iter().enumerate().rev() {
            pre.push_str(&format!("let x{i}={}(&mut stack);", pop(*t)));
        }
        let args = (0..sig.args.len())
            .map(|i| format!(",x{i}"))
            .collect::<String>();
        pre.push_str("let r=pop_r(&mut stack);");
        let call = format!("interface_dispatch_{id}(heap,r{args})");
        if sig.ret == 'V' {
            Ok(format!("{pre}{call};"))
        } else {
            Ok(format!("{pre}stack.push(V::{}({call}));", variant(sig.ret)))
        }
    }
    // Cierre finito sobre implementadores cargados por el compilador; tipos no
    // registrados abortan en ejecución en vez de despachar a otro método.
    fn interface_dispatch_source(&mut self) -> Result<String> {
        // Modo diagnóstico opt-in: los receptores omitidos abortan en el
        // despacho; nunca se usa para afirmar compatibilidad ni arrancar el servidor.
        let diagnostic_prefixes = std::env::var("MC_AOT_DIAGNOSTIC_DISPATCH_PREFIXES")
            .ok()
            .map(|s| {
                s.split(',')
                    .filter(|x| !x.is_empty())
                    .map(str::to_owned)
                    .collect::<Vec<_>>()
            });
        let admitted = |name: &str| {
            diagnostic_prefixes
                .as_ref()
                .map_or(true, |p| p.iter().any(|prefix| name.starts_with(prefix)))
        };
        let mut iface_arms: BTreeMap<usize, Vec<(String, String)>> = BTreeMap::new();
        let mut virtual_arms: BTreeMap<usize, Vec<(String, String)>> = BTreeMap::new();
        let mut iface_checked = BTreeSet::new();
        let mut virtual_checked = BTreeSet::new();
        let mut lambda_checked = BTreeSet::new();
        let mut lambda_arms: BTreeMap<usize, Vec<(usize, String)>> = BTreeMap::new();
        loop {
            let mut progress = false;
            let classes = self.multi_classes.as_ref().unwrap().clone();
            for (index, (interface, method, desc)) in
                self.interface_calls.clone().iter().enumerate()
            {
                for class in &classes {
                    if !iface_checked.insert((index, class.name.clone())) {
                        continue;
                    }
                    progress = true;
                    if (interface=="java/util/Spliterator" && class.name!="org/apache/logging/log4j/util/ServiceLoaderUtil$ServiceLoaderSpliterator")
                        || !admitted(&class.name)
                        || class.flags & (0x0200 | 0x0400) != 0
                        || !self.class_interfaces(&class.name)?.contains(interface)
                    {
                        continue;
                    }
                    if let Some(declaring) =
                        self.virtual_implementation(&class.name, method, desc)?
                    {
                        let data = class_from_jar(self.jar, &declaring)?;
                        let meta = super::metadata::parse(&data)?;
                        let public = meta.methods.iter().any(|m| {
                            m.name == *method && m.descriptor == *desc && m.flags & 0x0001 != 0
                        });
                        if !public {
                            continue;
                        }
                        let f = self.compile_instance(&declaring, method, desc)?;
                        iface_arms
                            .entry(index)
                            .or_default()
                            .push((class.name.clone(), f));
                    }
                }
            }
            for (index, (interface, method, desc)) in
                self.interface_calls.clone().iter().enumerate()
            {
                for (lambda_id, lambda) in self.lambdas.clone().iter().enumerate() {
                    if !lambda_checked.insert((index, lambda_id)) {
                        continue;
                    }
                    progress = true;
                    if project_class(&lambda.impl_owner) && !admitted(&lambda.impl_owner) {
                        continue;
                    }
                    if (lambda.interface != *interface
                        && !(lambda.interface == "java/util/function/BinaryOperator"
                            && interface == "java/util/function/BiFunction"))
                        || lambda.sam_name != *method
                        || lambda.sam_desc != *desc
                    {
                        continue;
                    }
                    // Solo modo diagnóstico: llamadas a lambdas Minecraft no traducidas
                    // abortan al ejecutarse. No se usa para fabricar un servidor.
                    if std::env::var("MC_AOT_GUARD_MINECRAFT_LAMBDAS").as_deref() == Ok("1")
                        && lambda.impl_owner.starts_with("net/minecraft/")
                    {
                        lambda_arms.entry(index).or_default().push((
                            lambda_id,
                            format!(
                                "error({:?})",
                                format!(
                                    "lambda Minecraft no compilada: {}.{}{}",
                                    lambda.impl_owner, lambda.impl_name, lambda.impl_desc
                                )
                            ),
                        ));
                        continue;
                    }
                    if lambda.impl_owner == "java/time/format/DateTimeFormatter"
                        || lambda.impl_owner == "java/time/Instant"
                        || lambda.impl_owner == "java/net/URI"
                        || lambda.impl_owner == "java/security/Key"
                    {
                        lambda_arms.entry(index).or_default().push((
                            lambda_id,
                            "error(\"invocación lambda JDK no soportada\")".into(),
                        ));
                        continue;
                    }
                    let inst = super::metadata::method_descriptor(&lambda.instantiated)?;
                    let sam = super::metadata::method_descriptor(&lambda.sam_desc)?;
                    let mut checks = String::new();
                    for (i, ty) in inst.args.iter().enumerate() {
                        if ty == &sam.args[i] {
                            continue;
                        }
                        let pred = match ty {
                            super::metadata::Type::Object(n) if n == "java/lang/Object" => None,
                            super::metadata::Type::Object(n) if n == "java/lang/String" => {
                                Some(format!("builtin_instance(heap,a{i},\"s\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/util/stream/Stream" => {
                                Some(format!("builtin_instance(heap,a{i},\"stream\")"))
                            }
                            super::metadata::Type::Object(n)
                                if n == "java/lang/StackWalker$StackFrame" =>
                            {
                                Some(format!("builtin_instance(heap,a{i},\"stackframe\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/lang/Class" => {
                                Some(format!("builtin_instance(heap,a{i},\"class\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/lang/Integer" => {
                                Some(format!("builtin_instance(heap,a{i},\"integer\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/util/List" => {
                                Some(format!("builtin_instance(heap,a{i},\"list\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/util/UUID" => {
                                Some(format!("builtin_instance(heap,a{i},\"uuid\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/util/regex/Pattern" => {
                                Some(format!("builtin_instance(heap,a{i},\"pattern\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/lang/Long" => {
                                Some(format!("builtin_instance(heap,a{i},\"long\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/lang/Float" => {
                                Some(format!("builtin_instance(heap,a{i},\"float\")"))
                            }
                            super::metadata::Type::Object(n) if n == "java/lang/Byte" => {
                                Some(format!("builtin_instance(heap,a{i},\"byte\")"))
                            }
                            super::metadata::Type::Object(n) if project_class(n) => Some(format!(
                                "project_instance(heap,a{i},{n:?},PROJECT_INTERFACES)"
                            )),
                            super::metadata::Type::Object(n) => {
                                return Err(format!("lambda adaptación JDK no soportada: {n}"))
                            }
                            super::metadata::Type::Array(_) => {
                                return Err("lambda adaptación array no soportada".into())
                            }
                            _ => None,
                        };
                        if let Some(pred) = pred {
                            checks.push_str(&format!(
                                "if a{i}.is_some()&&!{pred}{{raise(\"ClassCastException\",\"\");}}"
                            ));
                        }
                    }
                    let captures = signature_ext(&lambda.factory_desc, true)?;
                    let mut extraction = String::new();
                    for (i, t) in captures.args.iter().enumerate() {
                        let var = match t {
                            'J' => "L",
                            'F' => "F",
                            'D' => "D",
                            'I' | 'Z' | 'B' | 'C' | 'S' => "I",
                            _ if is_ref(*t) => "R",
                            _ => return Err("lambda captura no soportada".into()),
                        };
                        extraction.push_str(&format!("let c{i}=match captures[{i}]{{V::{var}(x)=>x,_=>panic!(\"tipo de captura lambda\")}};"));
                    }
                    let factory = super::metadata::method_descriptor(&lambda.factory_desc)?;
                    let target = super::metadata::method_descriptor(&lambda.impl_desc)?;
                    let mut from = factory.args;
                    from.extend(inst.args.clone());
                    let names = (0..captures.args.len())
                        .map(|i| format!("c{i}"))
                        .chain((0..inst.args.len()).map(|i| format!("a{i}")))
                        .collect::<Vec<_>>();
                    let mut expected = target.args.clone();
                    if matches!(lambda.impl_kind, 5 | 7 | 9) {
                        expected
                            .insert(0, super::metadata::Type::Object(lambda.impl_owner.clone()));
                    }
                    let mut actual = Vec::new();
                    for (i, ((name, source), dest)) in names
                        .iter()
                        .zip(from.iter())
                        .zip(expected.iter())
                        .enumerate()
                    {
                        if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Int) if n=="java/lang/Integer")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=integer_value(heap,{name});"));
                            actual.push(format!("unboxed{i}"));
                        } else if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Int) if n=="java/lang/Byte")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=byte_value(heap,{name}) as i32;"));
                            actual.push(format!("unboxed{i}"));
                        } else if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Byte) if n=="java/lang/Byte")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=byte_value(heap,{name});"));
                            actual.push(format!("unboxed{i}"));
                        } else if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Long) if n=="java/lang/Long")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=long_value(heap,{name});"));
                            actual.push(format!("unboxed{i}"));
                        } else if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Float) if n=="java/lang/Float")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=float_value(heap,{name});"));
                            actual.push(format!("unboxed{i}"));
                        } else if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Double) if n=="java/lang/Double")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=double_value(heap,{name});"));
                            actual.push(format!("unboxed{i}"));
                        } else if matches!((source,dest),(super::metadata::Type::Object(n),super::metadata::Type::Boolean) if n=="java/lang/Boolean")
                        {
                            extraction
                                .push_str(&format!("let unboxed{i}=boolean_value(heap,{name}) as i32;"));
                            actual.push(format!("unboxed{i}"));
                        } else {
                            actual.push(name.to_owned());
                        }
                    }
                    let args = actual.iter().map(|n| format!(",{n}")).collect::<String>();
                    let body = if (
                        lambda.impl_kind,
                        lambda.impl_owner.as_str(),
                        lambda.impl_name.as_str(),
                        lambda.impl_desc.as_str(),
                    ) == (9, "java/util/Set", "add", "(Ljava/lang/Object;)Z")
                    {
                        format!("collection_add(heap,{}, {}) as i32", actual[0], actual[1])
                    } else if (
                        lambda.impl_kind,
                        lambda.impl_owner.as_str(),
                        lambda.impl_name.as_str(),
                        lambda.impl_desc.as_str(),
                    ) == (
                        9,
                        "java/lang/StackWalker$StackFrame",
                        "getDeclaringClass",
                        "()Ljava/lang/Class;",
                    ) {
                        format!("Some(stack_frame_class(heap,{}))", actual[0])
                    } else if (lambda.impl_kind, lambda.impl_owner.as_str(), lambda.impl_name.as_str(), lambda.impl_desc.as_str()) == (9, "java/lang/StackWalker$StackFrame", "toStackTraceElement", "()Ljava/lang/StackTraceElement;") {
                        format!("{{let r={};array_id(heap,r);error(\"StackFrame.toStackTraceElement: método, línea y archivo no modelados\")}}", actual[0])
                    } else if (
                        lambda.impl_kind,
                        lambda.impl_owner.as_str(),
                        lambda.impl_name.as_str(),
                        lambda.impl_desc.as_str(),
                    ) == (6, "java/util/Objects", "nonNull", "(Ljava/lang/Object;)Z")
                    {
                        format!("({}.is_some()) as i32", actual[0])
                    } else if lambda.impl_owner == "java/util/UUID" {
                        format!("Some(uuid_string(heap,{}))", actual[0])
                    } else if (lambda.impl_kind, lambda.impl_owner.as_str(), lambda.impl_name.as_str(), lambda.impl_desc.as_str()) == (9, "java/util/Map$Entry", "getKey", "()Ljava/lang/Object;") {
                        format!("map_entry_key(heap,{})", actual[0])
                    } else if (lambda.impl_kind, lambda.impl_owner.as_str(), lambda.impl_name.as_str(), lambda.impl_desc.as_str()) == (6, "java/util/stream/Stream", "empty", "()Ljava/util/stream/Stream;") {
                        "Some(stream_empty(heap))".into()
                    } else if (lambda.impl_kind, lambda.impl_owner.as_str(), lambda.impl_name.as_str(), lambda.impl_desc.as_str()) == (9, "java/util/Map", "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;") {
                        format!("{{let _=map_put(heap,{0},{1},{2},false);}}", actual[0], actual[1], actual[2])
                    } else if (lambda.impl_kind, lambda.impl_owner.as_str(), lambda.impl_name.as_str(), lambda.impl_desc.as_str()) == (6, "java/util/List", "copyOf", "(Ljava/util/Collection;)Ljava/util/List;") {
                        format!("Some(list_copy_of(heap,{}))", actual[0])
                    } else if (lambda.impl_kind, lambda.impl_owner.as_str(), lambda.impl_name.as_str(), lambda.impl_desc.as_str()) == (8, "java/util/ArrayList", "<init>", "(Ljava/util/Collection;)V") {
                        format!("Some(list_construct_from_collection(heap,{}))", actual[0])
                    } else if lambda.impl_owner == "java/lang/Enum"
                        && lambda.impl_name == "toString"
                        && lambda.impl_desc == "()Ljava/lang/String;"
                    {
                        format!("enum_name(heap,{})", actual[0])
                    } else if lambda.impl_owner == "java/lang/Enum"
                        && lambda.impl_name == "ordinal"
                        && lambda.impl_desc == "()I"
                    {
                        format!("enum_ordinal(heap,{})", actual[0])
                    } else if lambda.impl_owner == "java/util/regex/Pattern" {
                        format!("pattern_string(heap,{})", actual[0])
                    } else if lambda.impl_owner == "java/lang/Character" {
                        format!("Some(character_to_string(heap,{}))", actual[0])
                    } else if lambda.impl_kind == 6 || lambda.impl_kind == 7 {
                        let f = if lambda.impl_kind == 7 {
                            extraction.push_str(&format!(
                                "let special_receiver=object_id(heap,{}, {:?});",
                                actual[0], lambda.impl_owner
                            ));
                            self.compile_instance(
                                &lambda.impl_owner,
                                &lambda.impl_name,
                                &lambda.impl_desc,
                            )?
                        } else {
                            self.compile(&lambda.impl_owner, &lambda.impl_name, &lambda.impl_desc)?
                        };
                        let args = if lambda.impl_kind == 7 {
                            format!(
                                ",special_receiver{}",
                                actual
                                    .iter()
                                    .skip(1)
                                    .map(|n| format!(",{n}"))
                                    .collect::<String>()
                            )
                        } else {
                            args.clone()
                        };
                        if matches!((&target.returns,&inst.returns),(super::metadata::Type::Long,super::metadata::Type::Object(n)) if n=="java/lang/Long")
                        {
                            format!("let result={f}(heap{args});Some(long_value_of(heap,result))")
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Object(n),super::metadata::Type::Boolean) if n=="java/lang/Boolean")
                        {
                            format!(
                                "let result={f}(heap{args});boolean_value(heap,result) as i32"
                            )
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Int,super::metadata::Type::Object(n)) if n=="java/lang/Integer")
                        {
                            format!(
                                "let result={f}(heap{args});Some(integer_value_of(heap,result))"
                            )
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Long,super::metadata::Type::Object(n)) if n=="java/lang/Long")
                        {
                            format!("let result={f}(heap{args});Some(long_value_of(heap,result))")
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Byte,super::metadata::Type::Object(n)) if n=="java/lang/Byte")
                        {
                            format!("let result={f}(heap{args});Some(byte_value_of(heap,result))")
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Float,super::metadata::Type::Object(n)) if n=="java/lang/Float")
                        {
                            format!("let result={f}(heap{args});Some(float_value_of(heap,result))")
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Double,super::metadata::Type::Object(n)) if n=="java/lang/Double")
                        {
                            format!("let result={f}(heap{args});Some(double_value_of(heap,result))")
                        } else if matches!((&target.returns,&inst.returns),(super::metadata::Type::Boolean,super::metadata::Type::Object(n)) if n=="java/lang/Boolean")
                        {
                            format!("let result={f}(heap{args});Some(boolean_value_of(heap,result!=0))")
                        } else {
                            format!("{f}(heap{args})")
                        }
                    } else if lambda.impl_kind == 8
                        && lambda.impl_owner == "java/lang/StringBuilder"
                    {
                        "Some(builder_new(heap))".into()
                    } else if lambda.impl_kind == 8 && lambda.impl_owner == "java/util/HashMap" {
                        "Some(hashmap_new(heap))".into()
                    } else if lambda.impl_kind == 8 && lambda.impl_owner == "java/io/BufferedOutputStream" {
                        let inner = &actual[0];
                        format!("Some(buffered_output_wrapped(heap, {inner}))")
                    } else if lambda.impl_kind == 8 {
                        let class_id = self.ensure_multi_class(&lambda.impl_owner)?;
                        let layout = self.instance_layout(&lambda.impl_owner)?;
                        let defaults = layout
                            .iter()
                            .map(|f| f.initial.clone())
                            .collect::<Vec<_>>()
                            .join(",");
                        let inherited =
                            self.multi_classes.as_ref().unwrap()[class_id].inheritable_local;
                        let f =
                            self.compile_instance(&lambda.impl_owner, "<init>", &lambda.impl_desc)?;
                        let owner = &lambda.impl_owner;
                        format!("init_class_{class_id}(heap);let obj=object_new(heap,{owner:?},vec![{defaults}],{inherited});{f}(heap,obj{args});Some(obj)")
                    } else if lambda.impl_owner == "java/lang/String" {
                        format!("Some(string_trim(heap,{}))", actual[0])
                    } else {
                        let receiver = &actual[0];
                        let params = actual
                            .iter()
                            .skip(1)
                            .map(|n| format!(",{n}"))
                            .collect::<String>();
                        let key = (
                            lambda.impl_owner.clone(),
                            lambda.impl_name.clone(),
                            lambda.impl_desc.clone(),
                        );
                        let id = if lambda.impl_kind == 9 {
                            self.interface_call(&key.0, &key.1, &key.2)?;
                            self.interface_calls
                                .iter()
                                .position(|k| *k == key)
                                .ok_or("lambda interface no registrada")?
                        } else {
                            self.virtual_call(&key.0, &key.1, &key.2)?;
                            self.virtual_calls
                                .iter()
                                .position(|k| *k == key)
                                .ok_or("lambda virtual no registrada")?
                        };
                        let dispatch = if lambda.impl_kind == 9 {
                            "interface"
                        } else {
                            "virtual"
                        };
                        format!("{dispatch}_dispatch_{id}(heap,{receiver}{params})")
                    };
                    let body = if inst.returns == super::metadata::Type::Void
                        && (target.returns != super::metadata::Type::Void || lambda.impl_kind == 8)
                    {
                        format!("{{{body};}}")
                    } else {
                        body
                    };
                    lambda_arms
                        .entry(index)
                        .or_default()
                        .push((lambda_id, format!("{checks}{extraction}{body}")));
                }
            }
            for (index, (owner, method, desc)) in self.virtual_calls.clone().iter().enumerate() {
                for class in &classes {
                    if !virtual_checked.insert((index, class.name.clone())) {
                        continue;
                    }
                    progress = true;
                    let is_object_root =
                        owner == "java/lang/Object" && project_class(&class.name);
                    if !admitted(&class.name)
                        || class.flags & (0x0200 | 0x0400) != 0
                        || (!is_object_root && !self.is_project_subclass(&class.name, owner))
                    {
                        continue;
                    }
                    // Guarda conservadora frente a overrides package-private entre paquetes.
                    if let Some(declaring) =
                        self.virtual_implementation(&class.name, method, desc)?
                    {
                        if !self.same_package_chain(&class.name, owner)
                            && !(self.cross_package_public_or_protected(owner, method, desc)?
                                && self
                                    .cross_package_public_or_protected(&declaring, method, desc)?)
                        {
                            if diagnostic_prefixes.is_some() {
                                continue;
                            }
                            return Err(format!(
                                "despacho virtual entre paquetes no soportado: {} como {owner}",
                                class.name
                            ));
                        }
                        let f = self.compile_instance(&declaring, method, desc)?;
                        virtual_arms
                            .entry(index)
                            .or_default()
                            .push((class.name.clone(), f));
                    }
                }
            }
            if !progress {
                break;
            }
        }
        fn emit(
            prefix: &str,
            calls: &[(String, String, String)],
            arms: &BTreeMap<usize, Vec<(String, String)>>,
            lambda_arms: &BTreeMap<usize, Vec<(usize, String)>>,
        ) -> Result<String> {
            let mut source = String::new();
            for (index, (owner, method, desc)) in calls.iter().enumerate() {
                let sig = signature_ext(desc, true)?;
                let params = sig
                    .args
                    .iter()
                    .enumerate()
                    .map(|(i, t)| format!(",a{i}:{}", rt(*t)))
                    .collect::<String>();
                let args = (0..sig.args.len())
                    .map(|i| format!(",a{i}"))
                    .collect::<String>();
                let cases = arms
                    .get(&index)
                    .into_iter()
                    .flatten()
                    .map(|(class, f)| format!("{class:?}=>{f}(heap,id{args}),"))
                    .collect::<String>();
                let label = if prefix == "interface" {
                    "invokeinterface"
                } else {
                    "invokevirtual"
                };
                let lambdas = if prefix == "interface" {
                    lambda_arms
                        .get(&index)
                        .into_iter()
                        .flatten()
                        .map(|(id, code)| format!("{id}=>{{{code}}},"))
                        .collect::<String>()
                } else {
                    String::new()
                };
                let identity = if prefix == "interface"
                    && (owner.as_str(), method.as_str(), desc.as_str())
                        == (
                            "java/util/function/Function",
                            "apply",
                            "(Ljava/lang/Object;)Ljava/lang/Object;",
                        ) {
                    "if matches!(heap.arrays[id],Array::IdentityFunction){return a0;}"
                } else {
                    ""
                };
                let compound_predicate = if prefix == "interface"
                    && (owner.as_str(), method.as_str(), desc.as_str())
                        == (
                            "java/util/function/Predicate",
                            "test",
                            "(Ljava/lang/Object;)Z",
                        ) {
                    format!("if let Array::Obj(\"java/util/function/Predicate\",fields)=&heap.arrays[id]{{if fields.len()==1{{if let V::R(Some(inner))=fields[0]{{let inner=*inner;let value={{let _opaque=call_guard(\"<jdk-callback>\");interface_dispatch_{index}(heap,Some(inner),a0)}};return if value==0{{1}}else{{0}};}}}}}}")
                } else {
                    String::new()
                };
                let sink = if prefix == "interface"
                    && (owner.as_str(), method.as_str(), desc.as_str())
                        == (
                            "java/util/function/Consumer",
                            "accept",
                            "(Ljava/lang/Object;)V",
                        ) {
                    let predicate = calls.iter().position(|(o, n, d)| {
                        (o.as_str(), n.as_str(), d.as_str())
                            == (
                                "java/util/function/Predicate",
                                "test",
                                "(Ljava/lang/Object;)Z",
                            )
                    });
                    if let Some(predicate) = predicate {
                        format!("if let Array::StreamSink(predicates,consumer)=&heap.arrays[id]{{let predicates=predicates.clone();let consumer=*consumer;for p in predicates{{let keep={{let _opaque=call_guard(\"<jdk-callback>\");interface_dispatch_{predicate}(heap,Some(p),a0)}};if keep==0{{return;}}}}let _opaque=call_guard(\"<jdk-callback>\");interface_dispatch_{index}(heap,Some(consumer),a0);return;}}")
                    } else {
                        String::new()
                    }
                } else {
                    String::new()
                };
                let target = format!("{owner}.{method}{desc}");
                let default = if prefix == "virtual"
                    && (owner.as_str(), method.as_str(), desc.as_str())
                        == (
                            "java/lang/Object",
                            "hashCode",
                            "()I",
                        ) {
                    "_=>object_identity_hash(r),".to_string()
                } else {
                    format!("_=>error(&format!(\"{label}: tipo o método no precompilado: {{class}} para {{}}\",{target:?}))")
                };
                source.push_str(&format!("fn {prefix}_dispatch_{index}(heap:&mut Heap,r:Option<usize>{params})->{}{{let id=array_id(heap,r);{identity}{compound_predicate}{sink}if let Array::Lambda(n,_,values)=&heap.arrays[id]{{let n=*n;let captures=values.clone();return match n{{{lambdas}_=>error(\"{label}: lambda no precompilada\")}};}}let class=match &heap.arrays[id]{{Array::Obj(c,_)|Array::SharedObj(c,_)|Array::LocalObj(c,_,_)=>*c,_=>error(\"despacho: objeto no soportado\")}};match class{{{cases}{default}}}}}\n",rt(sig.ret)));
            }
            Ok(source)
        }
        Ok(emit(
            "interface",
            &self.interface_calls,
            &iface_arms,
            &lambda_arms,
        )? + &emit("virtual", &self.virtual_calls, &virtual_arms, &lambda_arms)?)
    }
    fn special_call(
        &mut self,
        caller: &str,
        owner: &str,
        method: &str,
        desc: &str,
    ) -> Result<String> {
        let caller_id = self.ensure_multi_class(caller)?;
        let owner_id = self.ensure_multi_class(owner)?;
        if self.multi_classes.as_ref().unwrap()[owner_id].flags & 0x0200 != 0 {
            return Err(format!(
                "invokespecial de default no soportado: {owner}.{method}"
            ));
        }
        if caller == owner {
            return self.instance_call(owner, method, desc);
        }
        if !self.is_project_subclass(caller, owner) {
            return Err(format!(
                "invokespecial de superclase inválida: {caller} -> {owner}"
            ));
        }
        let parent = self.multi_classes.as_ref().unwrap()[caller_id]
            .parent
            .ok_or("invokespecial sin superclase")?;
        let parent_name = self.multi_classes.as_ref().unwrap()[parent].name.clone();
        let target = self
            .virtual_implementation(&parent_name, method, desc)?
            .ok_or_else(|| format!("invokespecial: método no resuelto {owner}.{method}{desc}"))?;
        self.instance_call(&target, method, desc)
    }
    fn instance_call(&mut self, owner: &str, method: &str, desc: &str) -> Result<String> {
        let sig = signature_ext(desc, true)?;
        let target = self.compile_instance(owner, method, desc)?;
        let mut pre = String::new();
        for (i, t) in sig.args.iter().enumerate().rev() {
            pre.push_str(&format!("let x{i}={}(&mut stack); ", pop(*t)));
        }
        let args = (0..sig.args.len())
            .map(|i| format!("x{i}"))
            .collect::<Vec<_>>()
            .join(",");
        let comma = if args.is_empty() {
            String::new()
        } else {
            format!(",{args}")
        };
        pre.push_str(&format!(
            "let r=pop_r(&mut stack);let id=object_id(heap,r,{owner:?}); "
        ));
        let call = format!("{target}(heap,id{comma})");
        if sig.ret == 'V' {
            Ok(format!("{pre}{call};"))
        } else {
            Ok(format!("{pre}stack.push(V::{}({call}));", variant(sig.ret)))
        }
    }
    fn compile(&mut self, class: &str, name: &str, desc: &str) -> Result<String> {
        if self.static_fields.is_some() && class != self.class_name {
            let data = class_from_jar(self.jar, class)?;
            let meta = super::metadata::parse(&data)?;
            if meta.name != class
                || meta.parent.as_deref() != Some("java/lang/Object")
                || !meta.interfaces.is_empty()
                || (meta.flags & 0x0200) != 0
                || meta.methods.iter().any(|m| m.name == "<clinit>")
                || meta.fields.iter().any(|f| {
                    f.flags & 0x0008 != 0
                        && (f.flags & 0x0040 != 0
                            || f.descriptor.len() != 1
                            || !"IJZBCS".contains(&f.descriptor))
                })
            {
                return Err(format!(
                    "clase auxiliar requiere inicialización no soportada: {class}"
                ));
            }
        }
        let class_init = if self.multi_classes.is_some() {
            Some(self.ensure_multi_class(class)?)
        } else {
            None
        };
        let sig = signature_ext(desc, self.multi_classes.is_some())?;
        let key = format!("{class}.{name}{desc}");
        let cache_key = format!("static:{key}");
        if self.multi_classes.is_some() {
            if let Some(f) = self.compiled_methods.get(&cache_key) {
                return Ok(f.clone());
            }
        } else if self.active.contains(&key) {
            return Err(format!("recursión no soportada: {key}"));
        }
        if self.active.len() >= 32 {
            return Err("profundidad de llamadas mayor a 32".into());
        }
        let mut declaring = class.to_owned();
        let mut fetched = if class == self.class_name {
            None
        } else {
            Some(class_from_jar(self.jar, class)?)
        };
        let mut method = find_method_with_handlers(
            fetched.as_deref().unwrap_or(self.class_data),
            name,
            desc,
            true,
        );
        {
            // La máquina virtual resuelve el propietario estático caminando la
            // jerarquía de superclases cuando la clase que nombra el sitio no
            // declara el método (por ejemplo ImmutableBiMap hereda entryOf de
            // ImmutableMap). Aquí ocurre lo mismo: solo si el fallo es
            // "no encontrado", y sin inventar nada.
            let missing = format!("no se encontró el método static {name}{desc} con Code");
            while matches!(&method, Err(e) if *e == missing) && declaring != "java/lang/Object" {
                let parsed = if declaring == self.class_name {
                    super::metadata::parse(self.class_data)?
                } else {
                    match &fetched {
                        Some(d) => super::metadata::parse(d)?,
                        None => super::metadata::parse(self.class_data)?,
                    }
                };
                let Some(parent) = parsed.parent else { break };
                if parent.starts_with('[') {
                    break;
                }
                declaring = parent;
                fetched = Some(class_from_jar(self.jar, &declaring).map_err(|_| format!(
                    "el método static {name}{desc} no aparece en {class} ni en la superclase {declaring}"
                ))?);
                method = find_method_with_handlers(fetched.as_deref().unwrap(), name, desc, true);
            }
        }
        let method = method?;
        let rust_name = format!("numeric_{}", self.serial);
        self.serial += 1;
        if self.multi_classes.is_some() {
            self.compiled_methods.insert(cache_key, rust_name.clone());
        }
        self.active.push(key.clone());
        let pump = if declaring == "net/minecraft/server/MinecraftServer" && name == "tickServer" && desc == "(Ljava/util/function/BooleanSupplier;)V" {Some("scheduled_pool_poll(heap);\n    ")} else {None};
        let compiled = self.lower(
            &method,
            &sig,
            &rust_name,
            &declaring,
            if name == "<clinit>" { None } else { class_init },
            false,
            pump,
        );
        self.active.pop();
        self.functions
            .push(compiled.map_err(|e| format!("{e}\n  al compilar {key}"))?);
        Ok(rust_name)
    }
    fn lambda_assignable(
        &self,
        from: &super::metadata::Type,
        to: &super::metadata::Type,
    ) -> Result<bool> {
        use super::metadata::Type;
        if from == to {
            return Ok(true);
        }
        if matches!(to,Type::Object(n) if n=="java/lang/Object")
            && matches!(from, Type::Object(_) | Type::Array(_))
        {
            return Ok(true);
        }
        // Borrado simétrico: un MethodHandle con retorno/parámetro java/lang/Object
        // puede usarse como lambda instanciada a cualquier referencia (LambdaMetafactory realiza el cast).
        if matches!(from,Type::Object(n) if n=="java/lang/Object")
            && matches!(to, Type::Object(_) | Type::Array(_))
        {
            return Ok(true);
        }
        let (from, to) = match (from, to) {
            (Type::Object(f), Type::Object(t)) => (f, t),
            _ => return Ok(false),
        };
        let mut todo = vec![from.to_owned()];
        let mut seen = BTreeSet::new();
        while let Some(name) = todo.pop() {
            if name == *to {
                return Ok(true);
            }
            if !seen.insert(name.clone()) {
                continue;
            }
            if !project_class(&name) {
                let parents: &[&str] = match name.as_str() {
                    "java/util/List" | "java/util/Set" => &["java/util/Collection"],
                    "java/util/SequencedSet" => &["java/util/Set"],
                    "java/util/SequencedCollection" => &["java/util/Collection"],
                    "java/util/SequencedMap" => &["java/util/Map"],
                    "java/util/SortedSet" | "java/util/NavigableSet" => &["java/util/SequencedSet"],
                    "java/util/SortedMap" | "java/util/NavigableMap" => &["java/util/SequencedMap"],
                    "java/util/Collection" => &["java/lang/Iterable"],
                    "java/util/HashMap" => &["java/util/Map"],
                    "java/io/BufferedOutputStream" => &["java/io/OutputStream"],
                    "java/util/HashSet" => &["java/util/Set"],
                    "java/util/LinkedHashSet" => &["java/util/HashSet"],
                    "java/util/TreeSet" => &["java/util/NavigableSet"],
                    "java/util/ArrayList" => &["java/util/List"],
                    "java/security/PublicKey" | "java/security/PrivateKey" => {
                        &["java/security/Key"]
                    }
                    _ => &[],
                };
                todo.extend(parents.iter().map(|x| x.to_string()));
                continue;
            }
            let data = class_from_jar(self.jar, &name)?;
            let meta = super::metadata::parse(&data)?;
            if let Some(parent) = meta.parent {
                todo.push(parent);
            }
            todo.extend(meta.interfaces);
        }
        Ok(false)
    }
    fn invoke_dynamic(&mut self, m: &Method, class: &str, index: u16) -> Result<String> {
        let (bootstrap, nt) = match m.cp.get(index as usize) {
            Some(CpEntry::InvokeDynamic(b, n)) => (*b, *n),
            _ => return Err("invokedynamic sin CONSTANT_InvokeDynamic".into()),
        };
        if !self.bootstrap_cache.contains_key(class) {
            let data = if class == self.class_name {
                self.class_data.to_vec()
            } else {
                class_from_jar(self.jar, class)?
            };
            self.bootstrap_cache
                .insert(class.to_owned(), super::bootstrap_methods(&data)?);
        }
        let b = self.bootstrap_cache[class]
            .get(bootstrap as usize)
            .ok_or("índice BootstrapMethods fuera de rango")?
            .clone();
        let target = match m.cp.get(b.method as usize) {
            Some(CpEntry::MethodHandle(6, i)) => *i,
            _ => return Err("bootstrap no es REF_invokeStatic".into()),
        };
        let (owner, method, desc) = method_ref(&m.cp, target)?;
        if (owner,method,desc)!=("java/lang/invoke/LambdaMetafactory","metafactory","(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodHandle;Ljava/lang/invoke/MethodType;)Ljava/lang/invoke/CallSite;") {return self.string_concat(m,class,index);}
        use super::metadata::Type;
        let (sam_name, factory_desc) = match m.cp.get(nt as usize) {
            Some(CpEntry::NameType(n, d)) => (
                super::utf(&m.cp, *n)?.to_owned(),
                super::utf(&m.cp, *d)?.to_owned(),
            ),
            _ => return Err("lambda NameAndType inválido".into()),
        };
        let factory = super::metadata::method_descriptor(&factory_desc)?;
        signature_ext(&factory_desc, true)?;
        let interface = match &factory.returns {
            Type::Object(n) => n.clone(),
            _ => return Err("lambda sin interfaz de retorno".into()),
        };
        self.verify_cast_interface(&interface)?;
        if b.arguments.len() != 3 {
            return Err("lambda metafactory argumentos inválidos".into());
        }
        let method_type = |idx: u16| -> Result<String> {
            match m.cp.get(idx as usize) {
                Some(CpEntry::MethodType(n)) => Ok(super::utf(&m.cp, *n)?.to_owned()),
                _ => Err("lambda MethodType inválido".into()),
            }
        };
        let sam_desc = method_type(b.arguments[0])?;
        let instantiated = method_type(b.arguments[2])?;
        if !project_class(&interface) && !jdk_function_method(&interface, &sam_name, &sam_desc) {
            return Err(format!(
                "lambda interfaz JDK no soportada: {interface}.{sam_name}{sam_desc}"
            ));
        }
        let (impl_kind, implementation) = match m.cp.get(b.arguments[1] as usize) {
            Some(CpEntry::MethodHandle(kind @ (5 | 6 | 7 | 8 | 9), i)) => (*kind, *i),
            Some(CpEntry::MethodHandle(kind, i)) => {
                let (o, n, d) = method_ref(&m.cp, *i)?;
                return Err(format!(
                    "lambda MethodHandle no soportado: REF_{kind} {o}.{n}{d}"
                ));
            }
            _ => return Err("lambda MethodHandle no soportado".into()),
        };
        let (impl_owner, impl_name, impl_desc) = method_ref(&m.cp, implementation)?;
        let jdk_ok = matches!(
            (impl_kind, impl_owner, impl_name, impl_desc),
            (6, "java/util/Objects", "nonNull", "(Ljava/lang/Object;)Z")
                | (9, "java/util/Map", "get", "(Ljava/lang/Object;)Ljava/lang/Object;")
                | (9, "java/util/Map", "containsKey", "(Ljava/lang/Object;)Z")
                | (9, "java/util/Set", "contains", "(Ljava/lang/Object;)Z")
                | (9, "java/util/Collection", "contains", "(Ljava/lang/Object;)Z")
                | (9, "java/util/List", "contains", "(Ljava/lang/Object;)Z")
                | (9, "java/util/Map", "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")
                | (9, "java/util/function/IntFunction", "apply", "(I)Ljava/lang/Object;")
                | (6, "java/util/stream/Stream", "empty", "()Ljava/util/stream/Stream;")
                | (9, "java/util/Map$Entry", "getKey", "()Ljava/lang/Object;")
                | (9, "java/util/Map$Entry", "getValue", "()Ljava/lang/Object;")
                | (9, "java/util/List", "indexOf", "(Ljava/lang/Object;)I")
                | (6, "java/util/List", "copyOf", "(Ljava/util/Collection;)Ljava/util/List;")
                | (8, "java/util/ArrayList", "<init>", "(Ljava/util/Collection;)V")
                | (
                    8,
                    "java/io/BufferedOutputStream",
                    "<init>",
                    "(Ljava/io/OutputStream;)V"
                )
                | (9, "java/util/Set", "add", "(Ljava/lang/Object;)Z")
                | (
                    9,
                    "java/lang/StackWalker$StackFrame",
                    "getDeclaringClass",
                    "()Ljava/lang/Class;"
                )
                | (9, "java/lang/StackWalker$StackFrame", "toStackTraceElement", "()Ljava/lang/StackTraceElement;")
                | (5, "java/lang/String", "trim", "()Ljava/lang/String;")
                | (8, "java/lang/StringBuilder", "<init>", "()V")
                | (8, "java/util/HashMap", "<init>", "()V")
                | (
                    5,
                    "java/time/format/DateTimeFormatter",
                    "format",
                    "(Ljava/time/temporal/TemporalAccessor;)Ljava/lang/String;"
                )
                | (
                    6,
                    "java/time/Instant",
                    "from",
                    "(Ljava/time/temporal/TemporalAccessor;)Ljava/time/Instant;"
                )
                | (5, "java/util/UUID", "toString", "()Ljava/lang/String;")
                | (
                    6,
                    "java/lang/Character",
                    "toString",
                    "(I)Ljava/lang/String;"
                )
                | (5, "java/net/URI", "toString", "()Ljava/lang/String;")
                | (5, "java/lang/Enum", "toString", "()Ljava/lang/String;")
                | (5, "java/lang/Enum", "ordinal", "()I")
                | (9, "java/security/Key", "getEncoded", "()[B")
                | (6, "java/lang/System", "nanoTime", "()J")
                | (6, "java/lang/System", "currentTimeMillis", "()J")
                | (
                    6,
                    "java/time/Instant",
                    "ofEpochMilli",
                    "(J)Ljava/time/Instant;"
                )
                | (5, "java/time/Instant", "toEpochMilli", "()J")
                | (
                    5,
                    "java/util/regex/Pattern",
                    "pattern",
                    "()Ljava/lang/String;"
                )
        );
        if !project_class(impl_owner) && !jdk_ok {
            return Err(format!(
                "lambda método JDK no soportado: {impl_owner}.{impl_name}{impl_desc}"
            ));
        }
        let implementation_type = super::metadata::method_descriptor(impl_desc)?;
        let sam = super::metadata::method_descriptor(&sam_desc)?;
        let inst = super::metadata::method_descriptor(&instantiated)?;
        let mut combined = factory.args.clone();
        combined.extend(inst.args.clone());
        let mut expected = implementation_type.args.clone();
        if matches!(impl_kind, 5 | 7 | 9) {
            expected.insert(0, Type::Object(impl_owner.to_owned()));
        }
        let args_ok = expected.len() == combined.len()
            && combined
                .iter()
                .zip(expected.iter())
                .map(|(f, t)| {
                    if matches!((f,t),(Type::Object(n),Type::Int) if n=="java/lang/Integer")
                        || matches!((f,t),(Type::Object(n),Type::Int) if n=="java/lang/Byte")
                        || matches!((f,t),(Type::Object(n),Type::Byte) if n=="java/lang/Byte")
                        || matches!((f,t),(Type::Object(n),Type::Float) if n=="java/lang/Float")
                        || matches!((f,t),(Type::Object(n),Type::Long) if n=="java/lang/Long")
                        || matches!((f,t),(Type::Object(n),Type::Double) if n=="java/lang/Double")
                        || matches!((f,t),(Type::Object(n),Type::Boolean) if n=="java/lang/Boolean")
                    {
                        Ok(true)
                    } else {
                        self.lambda_assignable(f, t)
                    }
                })
                .collect::<Result<Vec<_>>>()?
                .into_iter()
                .all(|v| v);
        let return_ok = if inst.returns == Type::Void {
            true
        } else if impl_kind != 8 {
            (matches!((&implementation_type.returns,&inst.returns),(Type::Int,Type::Object(n)) if n=="java/lang/Integer")
                || matches!((&implementation_type.returns,&inst.returns),(Type::Long,Type::Object(n)) if n=="java/lang/Long")
                || matches!((&implementation_type.returns,&inst.returns),(Type::Float,Type::Object(n)) if n=="java/lang/Float")
                || matches!((&implementation_type.returns,&inst.returns),(Type::Double,Type::Object(n)) if n=="java/lang/Double")
                || matches!((&implementation_type.returns,&inst.returns),(Type::Byte,Type::Object(n)) if n=="java/lang/Byte")
                || matches!((&implementation_type.returns,&inst.returns),(Type::Object(n),Type::Boolean) if n=="java/lang/Boolean")
                || matches!((&implementation_type.returns,&inst.returns),(Type::Boolean,Type::Object(n)) if n=="java/lang/Boolean")
                || self.lambda_assignable(&implementation_type.returns, &inst.returns)?)
        } else {
            impl_name == "<init>"
                && implementation_type.returns == Type::Void
                && self.lambda_assignable(&Type::Object(impl_owner.to_owned()), &inst.returns)?
        };
        if !args_ok || !return_ok {
            return Err(format!("lambda adaptación de implementación no soportada: kind={impl_kind} {impl_owner}.{impl_name}{impl_desc}; factory={factory_desc}; inst={instantiated}"));
        }
        // Compatibilidad de borrado instanciado <-> borrado del SAM: la máquina
        // virtual liga el handle por el descriptor instanciado, y los parámetros de
        // la implementación pueden ser un subtipo de los parámetros instanciados
        // (javac emite p.ej. Function<LivingEntity,List> & Allay::lambda$static$0).
        // Se conserva la igualdad para primitivos.
        let mut sam_ok = sam.args.len() == inst.args.len();
        if sam_ok {
            for (a, b) in sam.args.iter().zip(inst.args.iter()) {
                let ok = if matches!(a, Type::Object(_)|Type::Array(_)) && matches!(b, Type::Object(_)|Type::Array(_)) {
                    self.lambda_assignable(b, a)?
                } else {
                    a == b
                };
                if !ok {
                    sam_ok = false;
                    break;
                }
            }
        }
        if !sam_ok || !self.lambda_assignable(&inst.returns, &sam.returns)?
        {
            return Err(format!("lambda adaptación de parámetros no soportada: combined={combined:?} expected={expected:?} inst={instantiated} sam={sam_desc} impl={impl_owner}.{impl_name}{impl_desc}"));
        }
        signature_ext(&sam_desc, true)?;
        signature_ext(&instantiated, true)?;
        if project_class(impl_owner) {
            let data = class_from_jar(self.jar, impl_owner)?;
            let meta = super::metadata::parse(&data)?;
            if impl_kind == 6 || impl_kind == 8 {
                if !meta.methods.iter().any(|m| {
                    m.name == impl_name
                        && m.descriptor == impl_desc
                        && ((m.flags & 0x0008 != 0) == (impl_kind == 6))
                }) {
                    return Err("lambda método implementación no encontrado".into());
                }
            } else if impl_kind == 7 {
                // REF_invokeSpecial recurría a la máquina virtual al PRIMER argumento
                // del SAM como receptor (a.combine(b) ejecuta a.combine(b)), no a un
                // receptor capturado: en la práctica la captura puede ser cero
                // argumentos y el tipo estático del primer parámetro instanciado es
                // lo que liga. Se exige: el método existe, es privado no estático de
                // la propia clase, y el primer parámetro instanciado es una
                // referencia (borrada o exacta).
                if impl_owner != class
                    || !matches!(inst.args.first(),Some(Type::Object(_)|Type::Array(_)))
                    || !meta.methods.iter().any(|m| {
                        m.name == impl_name
                            && m.descriptor == impl_desc
                            && m.flags & 0x000a == 0x0002
                    })
                {
                    return Err("lambda REF_7: solo un método privado no estático de su propia clase, con el receptor como primer parámetro instanciado".into());
                }
            } else if impl_kind == 9 {
                self.verify_cast_interface(impl_owner)?;
            }
        }
        let site = (class.to_owned(), index);
        let id = if let Some(i) = self.lambdas.iter().position(|l| l.site == site) {
            i
        } else {
            let i = self.lambdas.len();
            self.lambdas.push(LambdaInfo {
                site,
                interface,
                sam_name,
                sam_desc,
                instantiated,
                factory_desc: factory_desc.clone(),
                impl_kind,
                impl_owner: impl_owner.to_owned(),
                impl_name: impl_name.to_owned(),
                impl_desc: impl_desc.to_owned(),
            });
            i
        };
        let n = factory.args.len();
        let receiver_guard=if impl_kind==7 {"if matches!(captures.first(),Some(V::R(None))){raise(\"NullPointerException\",\"\");}"} else {""};
        Ok(format!("let mut captures=Vec::with_capacity({n});for _ in 0..{n}{{captures.push(stack.pop().expect(\"captura lambda\"));}}captures.reverse();{receiver_guard}stack.push(V::R(Some(lambda_new(heap,{id},{:?},captures))));",self.lambdas[id].interface))
    }
    fn string_concat(&mut self, m: &Method, class: &str, index: u16) -> Result<String> {
        use super::metadata::Type;
        let (bootstrap, nt) = match m.cp.get(index as usize) {
            Some(CpEntry::InvokeDynamic(b, n)) => (*b, *n),
            _ => return Err("invokedynamic sin CONSTANT_InvokeDynamic".into()),
        };
        let (call_name, desc) = match m.cp.get(nt as usize) {
            Some(CpEntry::NameType(n, d)) => (super::utf(&m.cp, *n)?, super::utf(&m.cp, *d)?),
            _ => return Err("invokedynamic NameAndType inválido".into()),
        };
        let descriptor = super::metadata::method_descriptor(desc)?;
        if descriptor.returns != Type::Object("java/lang/String".into()) {
            return Err(format!("invokedynamic retorno no soportado: {desc}"));
        }
        for ty in &descriptor.args {
            if !matches!(
                ty,
                Type::Byte
                    | Type::Char
                    | Type::Int
                    | Type::Long
                    | Type::Short
                    | Type::Boolean
                    | Type::Object(_)
            ) {
                return Err(format!("invokedynamic concat tipo no soportado: {ty:?}"));
            }
            if let Type::Object(name) = ty {
                if name != "java/lang/String" && name != "java/lang/Object" {
                    return Err(format!(
                        "invokedynamic concat referencia no soportada: {name}"
                    ));
                }
            }
        }
        if !self.bootstrap_cache.contains_key(class) {
            let data = if class == self.class_name {
                self.class_data.to_vec()
            } else {
                class_from_jar(self.jar, class)?
            };
            self.bootstrap_cache
                .insert(class.to_owned(), super::bootstrap_methods(&data)?);
        }
        let b = self.bootstrap_cache[class]
            .get(bootstrap as usize)
            .ok_or("índice BootstrapMethods fuera de rango")?
            .clone();
        let target = match m.cp.get(b.method as usize) {
            Some(CpEntry::MethodHandle(6, i)) => *i,
            _ => return Err("bootstrap no es REF_invokeStatic".into()),
        };
        let (owner, method, bdesc) = method_ref(&m.cp, target)?;
        let with_constants="(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;Ljava/lang/invoke/MethodType;Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/invoke/CallSite;";
        let plain="(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;Ljava/lang/invoke/MethodType;)Ljava/lang/invoke/CallSite;";
        if owner != "java/lang/invoke/StringConcatFactory"
            || !((method == "makeConcatWithConstants" && bdesc == with_constants)
                || (method == "makeConcat" && bdesc == plain))
        {
            return Err(format!(
                "invokedynamic bootstrap no soportado: {owner}.{method}{bdesc}"
            ));
        }
        let units = |idx: u16| -> Result<Vec<u16>> {
            let utf_index = match m.cp.get(idx as usize) {
                Some(CpEntry::String(i)) => *i,
                _ => return Err("constante concat no String".into()),
            };
            match m.cp.get(utf_index as usize) {
                Some(CpEntry::Utf8(s)) => Ok(s.units.clone()),
                _ => Err("constante concat UTF8 inválida".into()),
            }
        };
        let (recipe, constants) = if method == "makeConcatWithConstants" {
            let (first, rest) = b.arguments.split_first().ok_or("concat sin receta")?;
            (units(*first)?, rest.to_vec())
        } else {
            if !b.arguments.is_empty() {
                return Err("makeConcat con constantes inválidas".into());
            }
            (vec![1u16; descriptor.args.len()], Vec::new())
        };
        let mut out = String::new();
        for (i, ty) in descriptor.args.iter().enumerate().rev() {
            let pop = match ty {
                Type::Long => "pop_l",
                Type::Object(_) => "pop_r",
                _ => "pop_i",
            };
            out.push_str(&format!("let x{i}={pop}(&mut stack);"));
        }
        out.push_str("let mut concat:Vec<u16>=Vec::new();");
        let mut arg = 0usize;
        let mut constant = 0usize;
        let mut literal = Vec::new();
        let flush = |out: &mut String, literal: &mut Vec<u16>| {
            if !literal.is_empty() {
                let entries = literal
                    .iter()
                    .map(|n| format!("{n}u16"))
                    .collect::<Vec<_>>()
                    .join(",");
                out.push_str(&format!("concat.extend_from_slice(&[{entries}]);"));
                literal.clear();
            }
        };
        for unit in recipe {
            if unit != 1 && unit != 2 {
                literal.push(unit);
                continue;
            }
            flush(&mut out, &mut literal);
            if unit == 1 {
                let ty = descriptor
                    .args
                    .get(arg)
                    .ok_or("receta concat con demasiados argumentos")?;
                let code = match ty {
                    Type::Object(_) => format!("concat_ref(heap,&mut concat,x{arg});"),
                    Type::Boolean => {
                        format!(
                            r#"concat.extend((if x{arg}!=0 {{"true"}}else{{"false"}}).encode_utf16());"#
                        )
                    }
                    Type::Char => format!("concat.push(x{arg} as u16);"),
                    Type::Byte => {
                        format!("concat.extend((x{arg} as i8).to_string().encode_utf16());")
                    }
                    Type::Short => {
                        format!("concat.extend((x{arg} as i16).to_string().encode_utf16());")
                    }
                    Type::Int | Type::Long => {
                        format!("concat.extend(x{arg}.to_string().encode_utf16());")
                    }
                    _ => unreachable!(),
                };
                out.push_str(&code);
                arg += 1;
            } else {
                let idx = *constants
                    .get(constant)
                    .ok_or("receta concat con demasiadas constantes")?;
                let text = match m.cp.get(idx as usize) {
                    Some(CpEntry::String(_)) => units(idx)?,
                    Some(CpEntry::Integer(i)) => i.to_string().encode_utf16().collect(),
                    Some(CpEntry::Long(i)) => i.to_string().encode_utf16().collect(),
                    _ => return Err("constante de bootstrap concat no soportada".into()),
                };
                literal.extend(text);
                constant += 1;
            }
        }
        flush(&mut out, &mut literal);
        if arg != descriptor.args.len() || constant != constants.len() {
            return Err(format!(
                "receta concat no coincide con argumentos: {call_name}{desc}"
            ));
        }
        out.push_str("stack.push(V::R(Some(new_string(heap,concat))));");
        Ok(out)
    }
    fn lower(
        &mut self,
        m: &Method,
        sig: &Sig,
        name: &str,
        class: &str,
        class_init: Option<usize>,
        instance: bool,
        pump: Option<&str>,
    ) -> Result<String> {
        // Only a closed hierarchy of runtime-generated exceptions is implemented.
        for handler in &m.handlers {
            if let Some(t) = &handler.catch_type {
                self.resolve_exception_type(t)?;
            }
        }
        let mut pos = if instance { 1 } else { 0 };
        let mut init = if instance {
            if m.locals == 0 {
                return Err("max_locals insuficiente para this".into());
            }
            format!("    check_object_class(heap,Some(this),{class:?}); locals[0]=Some(V::R(Some(this)));\n")
        } else {
            String::new()
        };
        for (i, t) in sig.args.iter().enumerate() {
            let width = if matches!(*t, 'J' | 'D') { 2 } else { 1 };
            if pos + width > m.locals {
                return Err("max_locals insuficiente para argumentos".into());
            }
            init.push_str(&format!(
                "    locals[{pos}]=Some(V::{}(a{i}));\n",
                variant(*t)
            ));
            pos += width;
        }
        let mut pc = 0usize;
        let mut arms = String::new();
        let summary = bytecode::scan(&m.code)?;
        let boundaries: BTreeSet<usize> = summary.boundaries.iter().copied().collect();
        let reachable = if self.multi_classes.is_some() {
            profile_reachable(m)?
        } else {
            None
        };
        let mut edges = Vec::new();
        while pc < m.code.len() {
            let start = pc;
            if reachable.as_ref().is_some_and(|r| !r.contains(&start)) {
                arms.push_str(&format!("        {start} => error(\"bytecode declarado inalcanzable por perfil Java 25\"),\n"));
                pc = boundaries
                    .range((start + 1)..)
                    .next()
                    .copied()
                    .unwrap_or(m.code.len());
                continue;
            }
            let op = m.code[pc];
            pc += 1;
            let mut read = || -> Result<u8> {
                let b = *m.code.get(pc).ok_or("instrucción truncada")?;
                pc += 1;
                Ok(b)
            };
            let mut fall = true;
            let mut branch = None;
            let body = match op {
                0x00 => String::new(),
                0x01 => "stack.push(V::R(None));".into(),
                0x02..=0x08 => format!("stack.push(V::I({}i32));",op as i8-3),
                0x09..=0x0a => format!("stack.push(V::L({}i64));",op-9),
                0x0b..=0x0d if self.multi_classes.is_some()=>format!("stack.push(V::F({}.0f32));",op-0x0b),
                0x0e..=0x0f if self.multi_classes.is_some()=>format!("stack.push(V::D({}.0f64));",op-0x0e),
                0x10 => format!("stack.push(V::I({}i32));",read()? as i8),
                0x11 => format!("stack.push(V::I({}i32));",i16::from_be_bytes([read()?,read()?])),
                0x12..=0x14 => {
                    let idx=if op==0x12 {read()? as u16} else {u16::from_be_bytes([read()?,read()?])};
                    match (op,m.cp.get(idx as usize)) {
                        (0x12|0x13,Some(CpEntry::Integer(n)))=>format!("stack.push(V::I({n}i32));"),
                        (0x14,Some(CpEntry::Long(n)))=>format!("stack.push(V::L({n}i64));"),
                        (0x12|0x13,Some(CpEntry::FloatBits(n))) if self.multi_classes.is_some()=>format!("stack.push(V::F(f32::from_bits({n}u32)));"),
                        (0x14,Some(CpEntry::DoubleBits(n))) if self.multi_classes.is_some()=>format!("stack.push(V::D(f64::from_bits({n}u64)));"),
                        (0x12|0x13,Some(CpEntry::Class(u))) if self.multi_classes.is_some()=>{
                            let target=super::utf(&m.cp,*u)?;
                            if matches!(target,"[Z"|"[B"|"[C"|"[S"|"[I"|"[J"|"[F"|"[D") { /* literales de arrays primitivos unidimensionales */ }
                            else if project_class(target) {self.ensure_class_literal(target)?;}
                            else if !matches!(target,"java/lang/Object"|"java/lang/Class"|"java/lang/String"|"java/lang/Runtime"|"java/lang/RuntimePermission"|"java/lang/Short"|"java/lang/Double"|"java/lang/Integer"|"java/lang/Boolean"|"java/lang/Character"|"java/lang/ThreadLocal"|"java/lang/InheritableThreadLocal"|"java/util/concurrent/ConcurrentHashMap"|"java/util/concurrent/LinkedBlockingQueue"|"java/util/ArrayList"|"java/util/HashSet"|"java/util/LinkedHashSet"|"java/util/UUID"|"java/time/Instant"|"java/nio/ByteBuffer"|"java/util/List"|"java/lang/Void"|"java/lang/Long"|"java/lang/Float"|"java/lang/Double"|"java/math/BigInteger"|"java/math/BigDecimal"|"java/sql/Timestamp"|"java/sql/Date"|"java/util/Date"|"java/util/Map"|"java/util/Collection"|"java/util/Set"|"java/util/TreeSet"|"java/util/Arrays"|"java/lang/Enum"|"java/util/concurrent/atomic/AtomicLong"|"java/util/concurrent/atomic/AtomicInteger"|"java/util/concurrent/atomic/AtomicBoolean"|"java/util/concurrent/atomic/AtomicLongArray"|"java/util/concurrent/atomic/AtomicIntegerArray"|"java/util/concurrent/ConcurrentSkipListMap"|"java/time/LocalDate"|"java/time/LocalTime"|"java/time/ZoneId"|"java/time/ZoneOffset"|"java/io/ObjectStreamClass"|"java/lang/Throwable"|"java/lang/Thread"|"java/security/PrivilegedExceptionAction"|"java/util/concurrent/locks/LockSupport"|"java/lang/ref/Reference"|"java/lang/reflect/TypeVariable"|"java/lang/reflect/ParameterizedType"|"java/lang/reflect/AnnotatedElement"|"java/io/IOException") {return Err(format!("literal Class no soportado: {target}"));}
                            self.class_literals.insert(target.to_owned());
                            format!("stack.push(V::R(Some(class_literal(heap,{target:?}))));")
                        },
                        (0x12|0x13,Some(CpEntry::String(u)))=>{
                            let units=match m.cp.get(*u as usize){Some(CpEntry::Utf8(v))=>&v.units,_=>return Err("String UTF inválida".into())};
                            let list=units.iter().map(|x|format!("{x}u16")).collect::<Vec<_>>().join(",");
                            format!("stack.push(V::R(Some(string_literal(heap,&[{list}]))));")
                        },
                        _=>return Err(format!("constante no soportada en {start}")),
                    }
                },
                0x15|0x16|0x1a..=0x21 => {
                    let (idx,t) = match op {
                        0x15 => (read()? as usize,'I'), 0x16 => (read()? as usize,'J'),
                        0x1a..=0x1d => ((op-0x1a) as usize,'I'), _ => ((op-0x1e) as usize,'J'),
                    };
                    if idx+(if t=='J'{2}else{1})>m.locals {return Err(format!("load fuera de rango en {start}"));}
                    format!("stack.push(V::{}(local_{}(&locals,{idx})));",variant(t),if t=='J'{"l"}else{"i"})
                },
                0x17|0x18|0x22..=0x29 if self.multi_classes.is_some()=>{
                    let (idx,t)=match op{0x17=>(read()? as usize,'F'),0x18=>(read()? as usize,'D'),0x22..=0x25=>((op-0x22) as usize,'F'),_=>((op-0x26) as usize,'D')};
                    if idx+(if t=='D'{2}else{1})>m.locals{return Err(format!("float load fuera de rango en {start}"));}
                    format!("stack.push(V::{}(local_{}(&locals,{idx})));",variant(t),if t=='D'{"d"}else{"f"})
                },
                0x19|0x2a..=0x2d => {
                    let idx=if op==0x19 {read()? as usize} else {(op-0x2a) as usize};
                    if idx>=m.locals {return Err(format!("aload fuera de rango en {start}"));}
                    format!("stack.push(V::R(local_r(&locals,{idx}))); ")
                },
                0x2e|0x2f|0x30|0x31|0x32|0x33|0x34|0x35 => format!("let i=pop_i(&mut stack); let a=pop_r(&mut stack); stack.push(array_load(heap,a,i,{op}));"),
                0x36|0x37|0x3b..=0x42 => {
                    let (idx,t) = match op {
                        0x36 => (read()? as usize,'I'), 0x37 => (read()? as usize,'J'),
                        0x3b..=0x3e => ((op-0x3b) as usize,'I'), _ => ((op-0x3f) as usize,'J'),
                    };
                    if idx+(if t=='J'{2}else{1})>m.locals {return Err(format!("store fuera de rango en {start}"));}
                    if t=='J' {format!("locals[{idx}]=Some(V::L(pop_l(&mut stack))); locals[{}]=None;",idx+1)}
                    else {format!("locals[{idx}]=Some(V::I(pop_i(&mut stack))); ")}
                },
                0x38|0x39|0x43..=0x4a if self.multi_classes.is_some()=>{
                    let (idx,t)=match op{0x38=>(read()? as usize,'F'),0x39=>(read()? as usize,'D'),0x43..=0x46=>((op-0x43) as usize,'F'),_=>((op-0x47) as usize,'D')};
                    if idx+(if t=='D'{2}else{1})>m.locals{return Err(format!("float store fuera de rango en {start}"));}
                    let extra=if t=='D'{format!("locals[{}]=None;",idx+1)}else{String::new()};format!("locals[{idx}]=Some(V::{}({}(&mut stack)));{extra}",variant(t),pop(t))
                },
                0x3a|0x4b..=0x4e => {
                    let idx=if op==0x3a {read()? as usize} else {(op-0x4b) as usize};
                    if idx>=m.locals {return Err(format!("astore fuera de rango en {start}"));}
                    format!("locals[{idx}]=Some(V::R(pop_r(&mut stack))); ")
                },
                0x4f|0x50|0x51|0x52|0x53|0x54|0x55|0x56 => format!("let v=stack.pop().expect(\"pila vacía\"); let i=pop_i(&mut stack); let a=pop_r(&mut stack); array_store(heap,a,i,v,{op});"),
                0x57 => "let v=stack.pop().expect(\"pila vacía\"); assert!(!matches!(v,V::L(_)|V::D(_)),\"pop de categoría 2\");".into(),
                0x58 => "let v=stack.pop().expect(\"pila vacía\"); if !matches!(v,V::L(_)|V::D(_)) {let u=stack.pop().expect(\"pila vacía\"); assert!(!matches!(u,V::L(_)|V::D(_)),\"pop2 inválido\");}".into(),
                0x59 => "let v=*stack.last().expect(\"pila vacía\"); assert!(!matches!(v,V::L(_)|V::D(_)),\"dup de categoría 2\"); stack.push(v);".into(),
                0x5a|0x5b|0x5d|0x5e => format!("stack_dup_x(&mut stack,{op});"),
                0x5c => "let v=*stack.last().expect(\"pila vacía\"); if matches!(v,V::L(_)|V::D(_)) {stack.push(v);} else {let n=stack.len(); assert!(n>=2,\"pila vacía\"); let u=stack[n-2]; assert!(!matches!(u,V::L(_)|V::D(_)),\"dup2 inválido\"); stack.push(u); stack.push(v);}".into(),
                0x5f => "let n=stack.len(); assert!(n>=2 && !matches!(stack[n-1],V::L(_)|V::D(_)) && !matches!(stack[n-2],V::L(_)|V::D(_)),\"swap inválido\"); stack.swap(n-1,n-2);".into(),
                0x60|0x64|0x68|0x6c|0x70|0x7e|0x80|0x82 => {
                    let expr=match op {0x60=>"a.wrapping_add(b)",0x64=>"a.wrapping_sub(b)",0x68=>"a.wrapping_mul(b)",0x6c=>"div_i(a,b)",0x70=>"rem_i(a,b)",0x7e=>"a & b",0x80=>"a | b",_=>"a ^ b"};
                    format!("let b=pop_i(&mut stack); let a=pop_i(&mut stack); stack.push(V::I({expr}));")
                },
                0x61|0x65|0x69|0x6d|0x71|0x7f|0x81|0x83 => {
                    let expr=match op {0x61=>"a.wrapping_add(b)",0x65=>"a.wrapping_sub(b)",0x69=>"a.wrapping_mul(b)",0x6d=>"div_l(a,b)",0x71=>"rem_l(a,b)",0x7f=>"a & b",0x81=>"a | b",_=>"a ^ b"};
                    format!("let b=pop_l(&mut stack); let a=pop_l(&mut stack); stack.push(V::L({expr}));")
                },
                0x62|0x66|0x6a|0x6e|0x72|0x63|0x67|0x6b|0x6f|0x73 if self.multi_classes.is_some()=>{
                    let t=if op%2==0{'F'}else{'D'};let operation=match op{0x62|0x63=>"+",0x66|0x67=>"-",0x6a|0x6b=>"*",0x6e|0x6f=>"/",_=>"%"};format!("let b={}(&mut stack);let a={}(&mut stack);stack.push(V::{}(a{operation}b));",pop(t),pop(t),variant(t))
                },
                0x76|0x77 if self.multi_classes.is_some()=>{let t=if op==0x76{'F'}else{'D'};format!("let a={}(&mut stack);stack.push(V::{}(-a));",pop(t),variant(t))},
                0x74=>"let a=pop_i(&mut stack); stack.push(V::I(a.wrapping_neg()));".into(),
                0x75=>"let a=pop_l(&mut stack); stack.push(V::L(a.wrapping_neg()));".into(),
                0x78|0x7a|0x7c => {
                    let expr=match op {0x78=>"a.wrapping_shl((b as u32)&31)",0x7a=>"a.wrapping_shr((b as u32)&31)",_=>"((a as u32)>>((b as u32)&31)) as i32"};
                    format!("let b=pop_i(&mut stack); let a=pop_i(&mut stack); stack.push(V::I({expr}));")
                },
                0x79|0x7b|0x7d => {
                    let expr=match op {0x79=>"a.wrapping_shl((b as u32)&63)",0x7b=>"a.wrapping_shr((b as u32)&63)",_=>"((a as u64)>>((b as u32)&63)) as i64"};
                    format!("let b=pop_i(&mut stack); let a=pop_l(&mut stack); stack.push(V::L({expr}));")
                },
                0x84 => {
                    let i=read()? as usize; let inc=read()? as i8;
                    if i>=m.locals {return Err(format!("iinc fuera de rango en {start}"));}
                    format!("locals[{i}]=Some(V::I(local_i(&locals,{i}).wrapping_add({inc}i32)));")
                },
                0x85=>"let a=pop_i(&mut stack); stack.push(V::L(a as i64));".into(),
                0x88=>"let a=pop_l(&mut stack); stack.push(V::I(a as i32));".into(),
                0x86|0x87|0x89|0x8a|0x8b|0x8c|0x8d|0x8e|0x8f|0x90 if self.multi_classes.is_some()=>{
                    let (src,dst)=match op{0x86=>('I','F'),0x87=>('I','D'),0x89=>('J','F'),0x8a=>('J','D'),0x8b=>('F','I'),0x8c=>('F','J'),0x8d=>('F','D'),0x8e=>('D','I'),0x8f=>('D','J'),_=>('D','F')};
                    format!("let a={}(&mut stack);stack.push(V::{}(a as {}));",pop(src),variant(dst),rt(dst))
                },
                0x95..=0x98 if self.multi_classes.is_some()=>{let t=if op<=0x96{'F'}else{'D'};let nan=if op==0x95||op==0x97{-1}else{1};format!("let b={}(&mut stack);let a={}(&mut stack);stack.push(V::I(if a.is_nan()||b.is_nan(){{{nan}}}else if a<b{{-1}}else if a>b{{1}}else{{0}}));",pop(t),pop(t))},
                0x91..=0x93=>{ let t=match op {0x91=>"i8",0x92=>"u16",_=>"i16"};format!("let a=pop_i(&mut stack); stack.push(V::I((a as {t}) as i32));") },
                0x94=>"let b=pop_l(&mut stack); let a=pop_l(&mut stack); stack.push(V::I(if a < b {-1} else if a > b {1} else {0}));".into(),
                0x99..=0xa4|0xa7 => {
                    let delta=i16::from_be_bytes([read()?,read()?]) as i64; let dest=target(start,delta)?;branch=Some(dest);
                    if op==0xa7 {fall=false;format!("pc={dest}; continue;")}
                    else { let cmp=match op {0x99|0x9f=>"==",0x9a|0xa0=>"!=",0x9b|0xa1=>"<",0x9c|0xa2=>">=",0x9d|0xa3=>">",_=>"<="};
                        if op<=0x9e {format!("let a=pop_i(&mut stack); if a {cmp} 0 {{pc={dest}; continue;}}")}
                        else {format!("let b=pop_i(&mut stack); let a=pop_i(&mut stack); if a {cmp} b {{pc={dest}; continue;}}")}
                    }
                },
                0xa5|0xa6|0xc6|0xc7 => {
                    let delta=i16::from_be_bytes([read()?,read()?]) as i64; let dest=target(start,delta)?;branch=Some(dest);
                    match op {
                        0xa5=>format!("let b=pop_r(&mut stack); let a=pop_r(&mut stack); if a==b {{pc={dest}; continue;}}"),
                        0xa6=>format!("let b=pop_r(&mut stack); let a=pop_r(&mut stack); if a!=b {{pc={dest}; continue;}}"),
                        0xc6=>format!("let a=pop_r(&mut stack); if a.is_none() {{pc={dest}; continue;}}"),
                        _=>format!("let a=pop_r(&mut stack); if a.is_some() {{pc={dest}; continue;}}"),
                    }
                },
                0xaa|0xab => {
                    let switch=bytecode::decode_switch(&m.code,start)?; let default=usize::try_from(switch.default).map_err(|_|"salto switch negativo")?;
                    edges.push(default); let mut cases=String::new();
                    for (key,dest) in switch.cases {let dest=usize::try_from(dest).map_err(|_|"salto switch negativo")?;edges.push(dest);cases.push_str(&format!("{key}i32 => {dest}usize, "));}
                    pc=switch.end;fall=false;format!("pc=match pop_i(&mut stack) {{ {cases}_ => {default}usize }}; continue;")
                },
                0xac|0xad => {
                    if is_ref(sig.ret) || matches!(sig.ret,'V'|'F'|'D') || (op==0xad)!=(sig.ret=='J') {return Err("tipo de retorno incompatible".into());}
                    fall=false; let v=if sig.ret=='J' {"pop_l(&mut stack)".to_string()} else {super::return_expr("pop_i(&mut stack)",sig.ret)};
                    format!("return {v};")
                },
                0xae|0xaf if self.multi_classes.is_some()=>{let t=if op==0xae{'F'}else{'D'};if sig.ret!=t{return Err("tipo de retorno float incompatible".into());}fall=false;format!("return {}(&mut stack);",pop(t))},
                0xb0 => {
                    if !is_ref(sig.ret) {return Err("areturn incompatible".into());}
                    fall=false; "return pop_r(&mut stack);".into()
                },
                0xb1 => {
                    if sig.ret!='V' {return Err("return void incompatible".into());}
                    fall=false; "return;".into()
                },
                0xb2|0xb3 => {
                    let index=u16::from_be_bytes([read()?,read()?]);
                    let (owner,field,desc)=super::object::field_ref(&m.cp,index)?;
                    if self.multi_classes.is_some() && op==0xb2 && (owner,field,desc)==("java/nio/charset/StandardCharsets","UTF_8","Ljava/nio/charset/Charset;") {"stack.push(V::R(Some(utf8_charset(heap))));".to_owned()}
                    else if self.multi_classes.is_some() && op==0xb2 && owner=="java/util/concurrent/TimeUnit" && desc=="Ljava/util/concurrent/TimeUnit;" && matches!(field,"NANOSECONDS"|"MICROSECONDS"|"MILLISECONDS"|"SECONDS"|"MINUTES"|"HOURS"|"DAYS") {let unit=match field{"NANOSECONDS"=>0,"MICROSECONDS"=>1,"MILLISECONDS"=>2,"SECONDS"=>3,"MINUTES"=>4,"HOURS"=>5,_=>6};format!("stack.push(V::R(Some(timeunit_get(heap,{unit}))));")}
                    else if self.multi_classes.is_some() && op==0xb2 && (owner,field,desc)==("java/util/Locale","ROOT","Ljava/util/Locale;") {"stack.push(V::R(Some(locale_root(heap))));".to_owned()}
                    else if self.multi_classes.is_some() && op==0xb2 && (owner,field,desc)==("java/time/format/DateTimeFormatter","ISO_INSTANT","Ljava/time/format/DateTimeFormatter;") {"stack.push(V::R(Some(iso_instant_formatter(heap))));".to_owned()}
                    else if self.multi_classes.is_some() && op==0xb2 && owner=="java/util/stream/Collector$Characteristics" && desc=="Ljava/util/stream/Collector$Characteristics;" && matches!(field,"UNORDERED"|"CONCURRENT"|"IDENTITY_FINISH") {
                        // Las características de un Collector son asesoras sobre ejecuciones
                        // paralelas; el perfil ejecuta streams secuenciales y solo puede
                        // construir la UNORDERED como marcador opaco.
                        "stack.push(V::R(Some(collector_characteristic(heap))));".to_owned()
                    } else if self.multi_classes.is_some() && op==0xb2 && owner=="java/lang/StackWalker$Option" && field=="RETAIN_CLASS_REFERENCE" && desc=="Ljava/lang/StackWalker$Option;" {
                        "stack.push(V::R(Some(stack_option(heap))));".to_owned()
                    } else                     if self.multi_classes.is_some() && op==0xb2 && owner=="java/lang/Boolean" && desc=="Ljava/lang/Boolean;" && matches!(field,"TRUE"|"FALSE") {
                        format!("stack.push(V::R(Some(boolean_value_of(heap,{}))));",field=="TRUE")
                    } else if self.multi_classes.is_some() && op==0xb2 && (owner,field,desc)==("java/net/Proxy","NO_PROXY","Ljava/net/Proxy;") {
                        "stack.push(V::R(Some(proxy_no_proxy(heap))));".to_owned()
                    } else                     if op==0xb2 && owner=="java/lang/System" && field=="out" && desc=="Ljava/io/PrintStream;" && self.static_fields.is_none() {
                        "stack.push(V::R(Some(stdout_ref(heap))));".to_owned()
                    } else if op==0xb2 && owner=="java/lang/System" && field=="err" && desc=="Ljava/io/PrintStream;" && self.multi_classes.is_some() {
                        "stack.push(V::R(Some(stderr_ref(heap))));".to_owned()
                    } else if self.multi_classes.is_some() && op==0xb2 && owner=="java/util/logging/Level" && desc=="Ljava/util/logging/Level;" && matches!(field,"ALL"|"FINEST"|"FINER"|"FINE"|"CONFIG"|"INFO"|"WARNING"|"SEVERE"|"OFF") {
                        format!("stack.push(V::R(Some(level_of(heap,{field:?}))));")
                    } else if self.multi_classes.is_some() && op==0xb2 && owner=="java/util/Locale" && desc=="Ljava/util/Locale;" && matches!(field,"US"|"ROOT"|"ENGLISH") {
                        // ASCII case mapping == Locale.ROOT; el receptor esta protegido por la guarda ASCII en el helper.
                        "stack.push(V::R(Some(locale_root(heap))));".into()
                    } else if self.multi_classes.is_some() {
                    let (id,slot,f)=self.resolve_static_field(owner,field,desc)?;
                    if op==0xb2 {format!("init_class_{id}(heap); stack.push(heap.fields[{slot}]);")}
                    else if is_ref(f.ty) {format!("let v=pop_r(&mut stack); init_class_{id}(heap); heap.fields[{slot}]=V::R(v);")}
                    else if f.ty=='J' {format!("let v=pop_l(&mut stack); init_class_{id}(heap); heap.fields[{slot}]=V::L(v);")}
                    else if matches!(f.ty,'F'|'D'){format!("let v={}(&mut stack);init_class_{id}(heap);heap.fields[{slot}]=V::{}(v);",pop(f.ty),variant(f.ty))}
                    else {let value=super::return_expr("v",f.ty);format!("let v=pop_i(&mut stack); init_class_{id}(heap); heap.fields[{slot}]=V::I({value});")}
                    } else {
                    if owner!=self.class_name || class!=self.class_name {return Err(format!("campo estático externo no soportado: {owner}.{field}{desc}"));}
                    let fields=self.static_fields.as_ref().ok_or("campos estáticos solo se admiten en static-demo")?;
                    let (slot,f)=fields.iter().enumerate().find(|(_,f)|f.name==field && desc.len()==1 && desc.starts_with(f.ty)).ok_or_else(||format!("campo estático no declarado: {owner}.{field}{desc}"))?;
                    if op==0xb2 {format!("stack.push(heap.fields[{slot}]);")}
                    else if f.ty=='J' {format!("heap.fields[{slot}]=V::L(pop_l(&mut stack));")}
                    else {let value=super::return_expr("pop_i(&mut stack)",f.ty);format!("heap.fields[{slot}]=V::I({value});")}
                    }
                },
                0xb4|0xb5 => {
                    if self.multi_classes.is_none(){return Err("campos de instancia solo en multi-static-demo".into());}
                    let idx=u16::from_be_bytes([read()?,read()?]);let (owner,field,desc)=super::object::field_ref(&m.cp,idx)?;
                    let (declaring,slot,f)=self.resolve_instance_field(owner,field,desc)?;
                    if op==0xb4 {format!("let r=pop_r(&mut stack);stack.push(object_load(heap,r,{declaring:?},{slot}));")}
                    else if is_ref(f.ty) {format!("let v=V::R(pop_r(&mut stack));let r=pop_r(&mut stack);object_store(heap,r,{declaring:?},{slot},v);")}
                    else if f.ty=='J' {format!("let v=V::L(pop_l(&mut stack));let r=pop_r(&mut stack);object_store(heap,r,{declaring:?},{slot},v);")}
                    else if matches!(f.ty,'F'|'D'){format!("let v=V::{}({}(&mut stack));let r=pop_r(&mut stack);object_store(heap,r,{declaring:?},{slot},v);",variant(f.ty),pop(f.ty))}
                    else {let value=super::return_expr("v",f.ty);format!("let v=pop_i(&mut stack);let r=pop_r(&mut stack);object_store(heap,r,{declaring:?},{slot},V::I({value}));")}
                },
                0xb6 => {
                    let idx=u16::from_be_bytes([read()?,read()?]);let (owner,name,desc)=method_ref(&m.cp,idx)?;
                    match (owner,name,desc) {
                        ("java/util/concurrent/CompletableFuture",_,_) if self.multi_classes.is_some()=>{
                            if !futures_optin()? {return Err("CompletableFuture: requiere MC_AOT_FUTURES=restricted (alias histórico MC_AOT_FUTURES=completed-only o MC_AOT_NUMERIC_COMPLETED_FUTURE=1)".into());}
                            match (name,desc) {
                                ("get"|"join","()Ljava/lang/Object;")=>"let r=pop_r(&mut stack);stack.push(V::R(completed_future_value(heap,r)));".into(),
                                ("getNow","(Ljava/lang/Object;)Ljava/lang/Object;")=>"let fallback=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(completed_future_get_now(heap,r,fallback)));".into(),
                                ("isDone","()Z")=>"let r=pop_r(&mut stack);stack.push(V::I(completed_future_is_done(heap,r)));".into(),
                                ("isCancelled"|"isCompletedExceptionally","()Z")=>"let r=pop_r(&mut stack);let _=completed_future_is_done(heap,r);stack.push(V::I(0));".into(),
                                ("complete","(Ljava/lang/Object;)Z")=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(completed_future_complete(heap,r,v)));".into(),
                                ("cancel","(Z)Z")=>return Err(format!("CompletableFuture.cancel no modelado: exigiría lanzar CancellationException sin estado soportado")),
                                _=>return Err(format!("CompletableFuture: operación no soportada: {name}{desc}")),
                            }
                        },
                        ("java/time/Duration","toNanos","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(duration_nanos(heap,r)));".into(),
                        ("java/time/Duration","toMillis","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(duration_millis(heap,r)));".into(),
                        ("java/time/Duration","getSeconds","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(duration_parts(heap,r).0));".into(),
                        ("java/time/Duration","getNano","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(duration_parts(heap,r).1));".into(),
                        ("java/net/URL","getProtocol","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(url_get_protocol(heap,r))));".into(),
                        ("java/net/URL","getHost","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(url_get_host(heap,r))));".into(),
                        ("java/net/URL","getPort","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(url_get_port(heap,r)));".into(),
                        ("java/net/URL","getFile","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(url_get_file(heap,r))));".into(),
                        ("java/net/URL","getQuery","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(url_get_query(heap,r)));".into(),
                        ("java/net/URL","toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(url_to_string(heap,r))));".into(),
                        ("java/net/URL","openConnection","()Ljava/net/URLConnection;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(http_connection_new(heap,r))));".into(),
                        ("java/net/URL","openConnection","(Ljava/net/Proxy;)Ljava/net/URLConnection;") if self.multi_classes.is_some()=>"let _proxy=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(http_connection_new(heap,r))));".into(),
                        ("java/net/HttpURLConnection","setRequestMethod","(Ljava/lang/String;)V") if self.multi_classes.is_some()=>"let m=pop_r(&mut stack);let r=pop_r(&mut stack);http_connection_set_request_method(heap,r,m);".into(),
                        ("java/net/HttpURLConnection","setRequestProperty","(Ljava/lang/String;Ljava/lang/String;)V") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let k=pop_r(&mut stack);let r=pop_r(&mut stack);http_connection_set_request_property(heap,r,k,v);".into(),
                        ("java/net/HttpURLConnection","setUseCaches","(Z)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);http_connection_set_use_caches(heap,r,v!=0);".into(),
                        ("java/net/HttpURLConnection","setDoOutput","(Z)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);http_connection_set_do_output(heap,r,v!=0);".into(),
                        ("java/net/HttpURLConnection","setDoInput","(Z)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);let _=http_connection_id(heap,r);let _=v;".into(),
                        ("java/net/HttpURLConnection","setConnectTimeout","(I)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);http_connection_set_connect_timeout(heap,r,v);".into(),
                        ("java/net/HttpURLConnection","setReadTimeout","(I)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);http_connection_set_read_timeout(heap,r,v);".into(),
                        ("java/net/HttpURLConnection","setIfModifiedSince","(J)V") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let r=pop_r(&mut stack);let _=v;let _=http_connection_id(heap,r);".into(),
                        ("java/net/HttpURLConnection","setInstanceFollowRedirects","(Z)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);let _=v;let _=http_connection_id(heap,r);".into(),
                        ("java/net/HttpURLConnection","getURL","()Ljava/net/URL;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(http_connection_get_url(heap,r))));".into(),
                        ("java/net/HttpURLConnection","getResponseCode","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","getHeaderField","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let k=pop_r(&mut stack);let r=pop_r(&mut stack);let _=k;http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","getInputStream","()Ljava/io/InputStream;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","getErrorStream","()Ljava/io/InputStream;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","getContentType","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","getOutputStream","()Ljava/io/OutputStream;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","connect","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_refuse(heap,r);".into(),
                        ("java/net/HttpURLConnection","disconnect","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);http_connection_disconnect(heap,r);".into(),
                        ("com/google/gson/GsonBuilder","create","()Lcom/google/gson/Gson;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(gson_builder_create(heap,r))));".into(),
                        ("com/google/gson/GsonBuilder","registerTypeAdapter","(Ljava/lang/reflect/Type;Ljava/lang/Object;)Lcom/google/gson/GsonBuilder;") if self.multi_classes.is_some()=>"let adapter=pop_r(&mut stack);let ty=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(gson_builder_register(heap,r,ty,adapter,false))));".into(),
                        ("com/google/gson/GsonBuilder","registerTypeHierarchyAdapter","(Ljava/lang/Class;Ljava/lang/Object;)Lcom/google/gson/GsonBuilder;") if self.multi_classes.is_some()=>"let adapter=pop_r(&mut stack);let ty=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(gson_builder_register(heap,r,ty,adapter,true))));".into(),
                        ("com/google/gson/Gson","fromJson","(Ljava/io/Reader;Ljava/lang/Class;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let _ty=pop_r(&mut stack);let _reader=pop_r(&mut stack);let r=pop_r(&mut stack);gson_from_json_unsupported(heap,r);".into(),
                        ("com/google/gson/Gson","fromJson","(Ljava/lang/String;Ljava/lang/Class;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let _ty=pop_r(&mut stack);let _reader=pop_r(&mut stack);let r=pop_r(&mut stack);gson_from_json_unsupported(heap,r);".into(),
                        ("com/google/gson/Gson","toJson","(Lcom/google/gson/JsonElement;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let _el=pop_r(&mut stack);let r=pop_r(&mut stack);gson_from_json_unsupported(heap,r);".into(),
                        ("com/google/gson/Gson","toJson","(Ljava/lang/Object;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let _el=pop_r(&mut stack);let r=pop_r(&mut stack);gson_from_json_unsupported(heap,r);".into(),
                        ("com/google/common/cache/CacheBuilder","expireAfterWrite","(Ljava/time/Duration;)Lcom/google/common/cache/CacheBuilder;") if self.multi_classes.is_some()=>"let d=pop_r(&mut stack);let r=pop_r(&mut stack);let ns=duration_nanos(heap,d);stack.push(V::R(Some(cache_expire_after_write(heap,r,ns))));".into(),
                        ("com/google/common/cache/CacheBuilder","expireAfterAccess","(Ljava/time/Duration;)Lcom/google/common/cache/CacheBuilder;") if self.multi_classes.is_some()=>"let d=pop_r(&mut stack);let r=pop_r(&mut stack);let ns=duration_nanos(heap,d);stack.push(V::R(Some(cache_expire_after_access(heap,r,ns))));".into(),
                        ("com/google/common/cache/CacheBuilder","maximumSize","(J)Lcom/google/common/cache/CacheBuilder;") if self.multi_classes.is_some()=>"let max=pop_l(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(cache_maximum_size(heap,r,max))));".into(),
                        ("com/google/common/cache/CacheBuilder","build","(Lcom/google/common/cache/CacheLoader;)Lcom/google/common/cache/LoadingCache;") if self.multi_classes.is_some()=>{self.interface_call("com/google/common/cache/CacheLoader","load","(Ljava/lang/Object;)Ljava/lang/Object;")?;let id=self.interface_calls.iter().position(|v|v.0=="com/google/common/cache/CacheLoader"&&v.1=="load"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("CacheLoader.load no registrada")?;format!("let loader=pop_r(&mut stack);let builder=pop_r(&mut stack);stack.push(V::R(Some(cache_build(heap,builder,loader,interface_dispatch_{id}))));").into()},
                        ("java/lang/StackWalker","walk","(Ljava/util/function/Function;)Ljava/lang/Object;") if self.multi_classes.is_some()=>{self.interface_call("java/util/function/Function","apply","(Ljava/lang/Object;)Ljava/lang/Object;")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/Function"&&v.1=="apply"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("Function.apply no registrada")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(stack_walk(heap,r,f,interface_dispatch_{id}))); ")},
                        ("java/lang/StackWalker","getCallerClass","()Ljava/lang/Class;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(stack_caller_class(heap,r))));".into(),
                        ("java/util/concurrent/atomic/AtomicInteger","get","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(atomic_integer_get(heap,r)));".into(),
                        ("java/util/concurrent/atomic/AtomicInteger","set","(I)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);atomic_integer_set(heap,r,v);".into(),
                        ("java/util/concurrent/atomic/AtomicInteger","getAndIncrement","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let old=atomic_integer_get(heap,r);atomic_integer_set(heap,r,old.wrapping_add(1));stack.push(V::I(old));".into(),
                        ("java/util/concurrent/atomic/AtomicInteger","incrementAndGet","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let v=atomic_integer_get(heap,r).wrapping_add(1);atomic_integer_set(heap,r,v);stack.push(V::I(v));".into(),
                        ("java/util/concurrent/atomic/AtomicInteger","compareAndSet","(II)Z") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let old=pop_i(&mut stack);let r=pop_r(&mut stack);let ok=atomic_integer_get(heap,r)==old;if ok{atomic_integer_set(heap,r,v);}stack.push(V::I(ok as i32));".into(),
                        ("java/util/concurrent/atomic/AtomicLong","get","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(atomic_long_get(heap,r)));".into(),
                        ("java/util/concurrent/atomic/AtomicLong","set","(J)V") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let r=pop_r(&mut stack);atomic_long_set(heap,r,v);".into(),
                        ("java/util/concurrent/atomic/AtomicLong","getAndSet","(J)J") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let r=pop_r(&mut stack);let old=atomic_long_get(heap,r);atomic_long_set(heap,r,v);stack.push(V::L(old));".into(),
                        ("java/util/concurrent/atomic/AtomicLong","compareAndSet","(JJ)Z") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let old=pop_l(&mut stack);let r=pop_r(&mut stack);let ok=atomic_long_get(heap,r)==old;if ok{atomic_long_set(heap,r,v);}stack.push(V::I(ok as i32));".into(),
                        ("java/util/concurrent/atomic/AtomicLong","getAndIncrement","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let old=atomic_long_get(heap,r);atomic_long_set(heap,r,old.wrapping_add(1));stack.push(V::L(old));".into(),
                        ("java/util/concurrent/atomic/AtomicLong","incrementAndGet","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let v=atomic_long_get(heap,r).wrapping_add(1);atomic_long_set(heap,r,v);stack.push(V::L(v));".into(),
                        ("java/util/concurrent/atomic/AtomicLong","updateAndGet","(Ljava/util/function/LongUnaryOperator;)J") if self.multi_classes.is_some()=>{self.interface_call("java/util/function/LongUnaryOperator","applyAsLong","(J)J")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/LongUnaryOperator"&&v.1=="applyAsLong"&&v.2=="(J)J").ok_or("LongUnaryOperator.applyAsLong no registrada")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::L(atomic_long_update_and_get(heap,r,f,interface_dispatch_{id})));").into()},
                        ("java/util/concurrent/atomic/AtomicReference","get","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(atomic_ref_get(heap,r)));".into(),
                        ("java/util/concurrent/atomic/AtomicReference","set","(Ljava/lang/Object;)V") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);atomic_ref_set(heap,r,v);".into(),
                        ("java/util/concurrent/atomic/AtomicReference","getAndSet","(Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);let old=atomic_ref_get(heap,r);atomic_ref_set(heap,r,v);stack.push(V::R(old));".into(),
                        ("java/util/concurrent/atomic/AtomicReference","compareAndSet","(Ljava/lang/Object;Ljava/lang/Object;)Z") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let old=pop_r(&mut stack);let r=pop_r(&mut stack);let ok=atomic_ref_get(heap,r)==old;if ok{atomic_ref_set(heap,r,v);}stack.push(V::I(ok as i32));".into(),
                        ("java/lang/Short","shortValue","()S") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(short_value(heap,r)));".into(),
                        ("java/lang/Double","doubleValue","()D") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::D(double_value(heap,r)));".into(),
                        ("java/lang/Float","floatValue","()F") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::F(float_value(heap,r)));".into(),
                        ("java/lang/Class","getResourceAsStream","(Ljava/lang/String;)Ljava/io/InputStream;") if self.multi_classes.is_some()=>{
                            let version=super::classpath::version_resource(self.jar)?;let embedded=match version{Some(data)=>format!("Some(&[{}])",data.iter().map(|b|format!("{b}u8")).collect::<Vec<_>>().join(",")),None=>"None".to_owned()};
                            format!("let name=pop_r(&mut stack);let class=pop_r(&mut stack);let stream=version_stream(heap,class,name,{embedded});stack.push(V::R(stream));")
                        },
                        ("java/net/URL","toURI","()Ljava/net/URI;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);array_id(heap,r);error(\"URL.toURI: URL no soportada\");".into(),
                        ("java/net/URL","openStream","()Ljava/io/InputStream;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);array_id(heap,r);error(\"URL.openStream: URL no soportada\");".into(),
                        ("java/net/URI","getPath","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(uri_path(heap,r))));".into(),
                        ("java/net/URI","getScheme","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(uri_scheme(heap,r))));".into(),
                        ("java/net/URI","toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(uri_string(heap,r))));".into(),
                        ("java/util/Properties","entrySet","()Ljava/util/Set;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(java_properties_entryset(heap,r))));".into(),
                        ("java/util/Properties","store","(Ljava/io/OutputStream;Ljava/lang/String;)V") if self.multi_classes.is_some()=>"let comment=pop_r(&mut stack);let output=pop_r(&mut stack);let r=pop_r(&mut stack);java_properties_store_eula(heap,r,output,comment);".into(),
                        ("java/io/OutputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);file_output_close(heap,r);".into(),
                        ("java/util/Properties","load","(Ljava/io/InputStream;)V") if self.multi_classes.is_some()=>"let input=pop_r(&mut stack);let r=pop_r(&mut stack);java_properties_load(heap,r,input);".into(),
                        ("java/util/Properties","getProperty","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let k=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(java_properties_get(heap,r,k,None)));".into(),
                        ("java/util/Properties","getProperty","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let fallback=pop_r(&mut stack);let k=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(java_properties_get(heap,r,k,fallback)));".into(),
                        ("java/util/Properties","setProperty","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let k=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(java_properties_set(heap,r,k,v)));".into(),
                        ("java/io/File","toPath","()Ljava/nio/file/Path;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(file_to_path(heap,r))));".into(),
                        ("java/io/File","exists","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(file_exists(heap,r) as i32));".into(),
                        ("java/security/KeyStore","load","(Ljava/io/InputStream;[C)V") if self.multi_classes.is_some()=>"let pw=pop_r(&mut stack);let in_=pop_r(&mut stack);let r=pop_r(&mut stack);let _=(pw,in_,r);error(\"KeyStore.load: no soportado (TLS auth chain; getInstance trapa antes)\");".into(),
                        ("javax/net/ssl/KeyManagerFactory","init","(Ljava/security/KeyStore;[C)V") if self.multi_classes.is_some()=>"let pw=pop_r(&mut stack);let ks=pop_r(&mut stack);let r=pop_r(&mut stack);let _=(pw,ks,r);error(\"KeyManagerFactory.init: no soportado (TLS auth chain)\");".into(),
                        ("javax/net/ssl/TrustManagerFactory","init","(Ljava/security/KeyStore;)V") if self.multi_classes.is_some()=>"let ks=pop_r(&mut stack);let r=pop_r(&mut stack);let _=(ks,r);error(\"TrustManagerFactory.init: no soportado (TLS trust chain)\");".into(),
                        ("java/io/File","isFile","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(file_is_file(heap,r) as i32));".into(),
                        ("java/io/File","isDirectory","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(file_is_directory(heap,r) as i32));".into(),
                        ("java/util/concurrent/locks/ReentrantLock","lock","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);reentrant_lock(heap,r);".into(),
                        ("java/util/concurrent/locks/ReentrantLock","unlock","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);reentrant_unlock(heap,r);".into(),
                        ("java/util/concurrent/locks/ReentrantLock","getHoldCount","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(reentrant_count(heap,r)));".into(),
                        ("java/util/concurrent/locks/ReentrantLock","isHeldByCurrentThread","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I((reentrant_count(heap,r)>0) as i32));".into(),
                        ("java/time/format/DateTimeFormatter","formatTo","(Ljava/time/temporal/TemporalAccessor;Ljava/lang/Appendable;)V") if self.multi_classes.is_some()=>r#"error("DateTimeFormatter.formatTo: formateo de fecha no implementado");"#.into(),
                        ("java/time/format/DateTimeFormatter","withZone","(Ljava/time/ZoneId;)Ljava/time/format/DateTimeFormatter;") if self.multi_classes.is_some()=>r#"error("DateTimeFormatter.withZone: zonas no implementadas");"#.into(),
                        ("java/lang/ref/WeakReference"|"java/lang/ref/Reference","get","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(weak_loader_get(heap,r)));".into(),
                        ("java/lang/ref/WeakReference"|"java/lang/ref/Reference","clear","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);weak_loader_set(heap,r,None);".into(),
                        ("java/lang/RuntimePermission"|"java/security/BasicPermission"|"java/security/Permission","getName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(runtime_permission_name(heap,r))));".into(),
                        ("java/lang/RuntimePermission"|"java/security/BasicPermission"|"java/security/Permission","getActions","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);runtime_permission_name(heap,r);stack.push(V::R(Some(string_literal(heap,&[]))));".into(),
                        ("java/lang/Runtime","availableProcessors","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(runtime_processors(heap,r)));".into(),
                        ("java/lang/Character","charValue","()C") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(unbox_character(heap,r)));".into(),
                        ("java/util/Map$Entry","getKey","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(map_entry_key(heap,r)));".into(),
                        ("java/util/Map$Entry","getValue","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(map_entry_value(heap,r)));".into(),
                        ("java/lang/CharSequence","toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(char_sequence_to_string(heap,r))));".into(),
                        ("java/lang/CharSequence","subSequence","(II)Ljava/lang/CharSequence;") if self.multi_classes.is_some()=>"let end=pop_i(&mut stack);let begin=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(char_sequence_subsequence(heap,r,begin,end))));".into(),
                        ("java/lang/CharSequence","length","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(char_sequence_length(heap,r)));".into(),
                        ("java/lang/CharSequence","charAt","(I)C") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(char_sequence_at(heap,r,i)));".into(),
                        ("java/io/InputStreamReader"|"java/io/Reader"|"java/io/StringReader","read","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(reader_read(heap,r)));".into(),
                        ("java/io/InputStreamReader"|"java/io/Reader"|"java/io/StringReader","read","([CII)I") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let dst=pop_r(&mut stack);let r=pop_r(&mut stack);let n=reader_read_chars(heap,r,dst,off,len);stack.push(V::I(n));".into(),
                        ("java/io/InputStreamReader"|"java/io/Reader","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);reader_close(heap,r);".into(),
                        ("java/io/StringReader","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);reader_close_string(heap,r);".into(),
                        ("java/io/BufferedReader","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);reader_close_string(heap,r);".into(),
                        ("java/io/BufferedReader","lines","()Ljava/util/stream/Stream;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);Some(buffered_reader_lines(heap,r))".into(),
                        ("java/io/BufferedOutputStream","write","(I)V") if self.multi_classes.is_some()=>"let b=pop_i(&mut stack);let r=pop_r(&mut stack);stream_write_byte(heap,r,b);".into(),
                        ("java/io/BufferedOutputStream","write","([B)V") if self.multi_classes.is_some()=>"let buf=pop_r(&mut stack);let r=pop_r(&mut stack);stream_write_array(heap,r,buf,0,-1);".into(),
                        ("java/io/BufferedOutputStream","write","([BII)V") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let buf=pop_r(&mut stack);let r=pop_r(&mut stack);stream_write_array(heap,r,buf,off,len);".into(),
                        ("java/io/BufferedOutputStream","flush","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);buffered_output_flush(heap,r);".into(),
                        ("java/io/BufferedOutputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);buffered_output_close(heap,r);".into(),
                        ("java/util/zip/GZIPOutputStream","write","(I)V") if self.multi_classes.is_some()=>"let b=pop_i(&mut stack);let r=pop_r(&mut stack);stream_write_byte(heap,r,b);".into(),
                        ("java/util/zip/GZIPOutputStream","write","([B)V") if self.multi_classes.is_some()=>"let buf=pop_r(&mut stack);let r=pop_r(&mut stack);stream_write_array(heap,r,buf,0,-1);".into(),
                        ("java/util/zip/GZIPOutputStream","write","([BII)V") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let buf=pop_r(&mut stack);let r=pop_r(&mut stack);stream_write_array(heap,r,buf,off,len);".into(),
                        ("java/util/zip/GZIPOutputStream","flush","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);gzip_out_flush(heap,r);".into(),
                        ("java/util/zip/GZIPOutputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);gzip_out_close(heap,r);".into(),
                        ("java/util/zip/DeflaterOutputStream","write","(I)V") if self.multi_classes.is_some()=>"let b=pop_i(&mut stack);let r=pop_r(&mut stack);stream_write_byte(heap,r,b);".into(),
                        ("java/util/zip/DeflaterOutputStream","write","([B)V") if self.multi_classes.is_some()=>"let buf=pop_r(&mut stack);let r=pop_r(&mut stack);stream_write_array(heap,r,buf,0,-1);".into(),
                        ("java/util/zip/DeflaterOutputStream","write","([BII)V") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let buf=pop_r(&mut stack);let r=pop_r(&mut stack);stream_write_array(heap,r,buf,off,len);".into(),
                        ("java/util/zip/DeflaterOutputStream","flush","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);deflate_out_flush(heap,r);".into(),
                        ("java/util/zip/DeflaterOutputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);deflate_out_close(heap,r);".into(),
                        ("java/util/zip/GZIPInputStream","read","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(gzip_in_read(heap,r)));".into(),
                        ("java/util/zip/GZIPInputStream","read","([B)I") if self.multi_classes.is_some()=>"let dst=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(deflate_read_into(heap,r,dst,0,-1,true)));".into(),
                        ("java/util/zip/GZIPInputStream","read","([BII)I") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let dst=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(deflate_read_into(heap,r,dst,off,len,true)));".into(),
                        ("java/util/zip/GZIPInputStream","available","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(compressed_available(heap,r,true)));".into(),
                        ("java/util/zip/GZIPInputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);resource_close(heap,r);".into(),
                        ("java/util/zip/InflaterInputStream","read","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(deflate_in_read(heap,r)));".into(),
                        ("java/util/zip/InflaterInputStream","read","([B)I") if self.multi_classes.is_some()=>"let dst=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(deflate_read_into(heap,r,dst,0,-1,false)));".into(),
                        ("java/util/zip/InflaterInputStream","read","([BII)I") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let dst=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(deflate_read_into(heap,r,dst,off,len,false)));".into(),
                        ("java/util/zip/InflaterInputStream","available","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(compressed_available(heap,r,false)));".into(),
                        ("java/util/zip/InflaterInputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);resource_close(heap,r);".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","read","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(resource_read(heap,r)));".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","read","([BII)I") if self.multi_classes.is_some()=>"let len=pop_i(&mut stack);let off=pop_i(&mut stack);let dst=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(byte_input_read_range(heap,r,dst,off,len)));".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","available","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(byte_input_available(heap,r)));".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","skip","(J)J") if self.multi_classes.is_some()=>"let n=pop_l(&mut stack);let r=pop_r(&mut stack);stack.push(V::L(byte_input_skip(heap,r,n)));".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","mark","(I)V") if self.multi_classes.is_some()=>"let _limit=pop_i(&mut stack);let r=pop_r(&mut stack);byte_input_mark(heap,r);".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","reset","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);byte_input_reset(heap,r);".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","markSupported","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);byte_input_available(heap,r);stack.push(V::I(1));".into(),
                        ("java/io/InputStream"|"java/io/ByteArrayInputStream","close","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);resource_close(heap,r);".into(),
                        ("java/time/ZonedDateTime","toInstant","()Ljava/time/Instant;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let x=zoned_to_instant(heap,r);stack.push(V::R(Some(x)));".into(),
                        ("java/util/Date","toInstant","()Ljava/time/Instant;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(date_to_instant(heap,r))));".into(),
                        ("java/time/Instant","toEpochMilli","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(instant_millis(heap,r)));".into(),
                        ("java/util/Date","getTime","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(date_get(heap,r)));".into(),
                        ("java/util/Date","setTime","(J)V") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let r=pop_r(&mut stack);date_set(heap,r,v);".into(),
                        ("java/util/UUID","toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let v=uuid_string(heap,r);stack.push(V::R(Some(v)));".into(),
                        ("java/util/BitSet","set","(I)V") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);bitset_set(heap,r,i);".into(),
                        ("java/util/BitSet","set","(IZ)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let i=pop_i(&mut stack);let r=pop_r(&mut stack);bitset_set_bool(heap,r,i,v);".into(),
                        ("java/util/BitSet","set","(II)V") if self.multi_classes.is_some()=>"let to=pop_i(&mut stack);let from=pop_i(&mut stack);let r=pop_r(&mut stack);bitset_set_range(heap,r,from,to);".into(),
                        ("java/util/BitSet","get","(I)Z") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(bitset_get(heap,r,i)));".into(),
                        ("java/util/BitSet","get","(II)Ljava/util/BitSet;") if self.multi_classes.is_some()=>"let to=pop_i(&mut stack);let from=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(bitset_get_range(heap,r,from,to))));".into(),
                        ("java/util/BitSet","isEmpty","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(bitset_is_empty(heap,r)));".into(),
                        ("java/util/BitSet","length","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(bitset_length(heap,r)));".into(),
                        ("java/util/BitSet","size","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(bitset_size(heap,r)));".into(),
                        ("java/util/BitSet","cardinality","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(bitset_cardinality(heap,r)));".into(),
                        ("java/util/BitSet","nextSetBit","(I)I") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(bitset_next_set_bit(heap,r,i)));".into(),
                        ("java/util/BitSet","nextClearBit","(I)I") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(bitset_next_clear_bit(heap,r,i)));".into(),
                        ("java/util/BitSet","clear","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);bitset_clear_all(heap,r);".into(),
                        ("java/util/BitSet","clear","(I)V") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);bitset_clear_one(heap,r,i);".into(),
                        ("java/util/BitSet","clear","(II)V") if self.multi_classes.is_some()=>"let to=pop_i(&mut stack);let from=pop_i(&mut stack);let r=pop_r(&mut stack);bitset_clear_range(heap,r,from,to);".into(),
                        ("java/util/BitSet","toLongArray","()[J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(bitset_to_longs(heap,r))));".into(),
                        ("java/util/BitSet","toByteArray","()[B") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(bitset_to_bytes(heap,r))));".into(),
                        ("java/util/BitSet","clone","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(bitset_clone(heap,r))));".into(),
                        ("java/util/BitSet","hashCode","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(bitset_hash_code(heap,r)));".into(),
                        ("java/util/BitSet","equals","(Ljava/lang/Object;)Z") if self.multi_classes.is_some()=>"let o=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(bitset_equals(heap,r,o)));".into(),
                        ("java/util/BitSet","stream","()Ljava/util/stream/IntStream;") if self.multi_classes.is_some()=>"{let r=pop_r(&mut stack);error(\"BitSet.stream no soportado en este perfil\")}".into(),
                        ("java/util/UUID","version","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(uuid_parts(heap,r).0 as i32));".into(),
                        ("java/util/UUID","variant","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(uuid_parts(heap,r).1 as i32));".into(),
                        ("java/lang/String","matches","(Ljava/lang/String;)Z") if self.multi_classes.is_some()=>"let p=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(string_matches_formatting(heap,r,p) as i32));".into(),
                        ("java/lang/String","replaceAll","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let repl=pop_r(&mut stack);let pattern=pop_r(&mut stack);let value=pop_r(&mut stack);let v=string_replace_dash(heap,value,pattern,repl);stack.push(V::R(Some(v)));".into(),
                        ("java/util/regex/Pattern","matcher","(Ljava/lang/CharSequence;)Ljava/util/regex/Matcher;") if self.multi_classes.is_some()=>"let input=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(pattern_matcher(heap,r,input))));".into(),
                        ("java/util/regex/Matcher","matches","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let _=array_id(heap,r);error(\"Matcher.matches: operación fuera del perfil implementado\");".into(),
                        ("java/util/regex/Matcher","replaceAll","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let repl=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(matcher_replace_all(heap,r,repl))));".into(),
                        ("java/util/regex/Matcher","find","(I)Z") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(matcher_find(heap,r,i) as i32));".into(),
                        ("java/util/regex/Matcher","end","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(matcher_end(heap,r)));".into(),
                        ("java/util/regex/Matcher","group","(I)Ljava/lang/String;") if self.multi_classes.is_some()=>"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(matcher_group(heap,r,i)));".into(),
                        ("java/util/regex/Pattern","flags","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(pattern_flags(heap,r)));".into(),
                        ("java/util/regex/Pattern","pattern"|"toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(pattern_string(heap,r)));".into(),
                        ("java/lang/Thread","getId"|"threadId","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(thread_id(heap,r)));".into(),
                        ("java/lang/Thread","getContextClassLoader","()Ljava/lang/ClassLoader;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(thread_context_loader(heap,r)));".into(),
                        ("java/lang/Thread","setContextClassLoader","(Ljava/lang/ClassLoader;)V") if self.multi_classes.is_some()=>"let loader=pop_r(&mut stack);let r=pop_r(&mut stack);thread_set_context_loader(heap,r,loader);".into(),
                        ("java/lang/Thread","getName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(thread_name(heap,r))));".into(),
                        ("java/lang/Thread","setName","(Ljava/lang/String;)V") if self.multi_classes.is_some()=>"let name=pop_r(&mut stack);let r=pop_r(&mut stack);thread_set_name_guard(heap,r,name);".into(),
                        ("java/lang/Thread","interrupt","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);thread_interrupt(heap,r);".into(),
                        ("java/lang/Thread","isInterrupted","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(thread_is_interrupted(heap,r) as i32));".into(),
                        ("java/util/Optional","map","(Ljava/util/function/Function;)Ljava/util/Optional;") if self.multi_classes.is_some()=>{self.interface_call("java/util/function/Function","apply","(Ljava/lang/Object;)Ljava/lang/Object;")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/Function"&&v.1=="apply"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("Function.apply no registrada")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);let v=optional_value(heap,r);let _=array_id(heap,f);let mapped=match v{{None=>None,Some(v)=>{{let _opaque=call_guard(\"<jdk-callback>\");interface_dispatch_{id}(heap,f,Some(v))}}}};stack.push(V::R(Some(optional_new(heap,mapped))));")},
                        ("java/util/Optional","isPresent","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(optional_value(heap,r).is_some() as i32));".into(),
                        ("java/util/Optional","isEmpty","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(optional_value(heap,r).is_none() as i32));".into(),
                        ("java/util/Optional","get","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(optional_value(heap,r).unwrap_or_else(||raise(\"NoSuchElementException\",\"No value present\")))));".into(),
                        ("java/util/Optional","orElseGet","(Ljava/util/function/Supplier;)Ljava/lang/Object;") if self.multi_classes.is_some()=>{self.interface_call("java/util/function/Supplier","get","()Ljava/lang/Object;")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/Supplier"&&v.1=="get"&&v.2=="()Ljava/lang/Object;").ok_or("Supplier.get no registrado")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);let v=match optional_value(heap,r){{Some(v)=>Some(v),None=>{{let _opaque=call_guard(\"<jdk-callback>\");interface_dispatch_{id}(heap,f)}}}};stack.push(V::R(v));")},
                        ("java/util/Optional","orElse","(Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(optional_value(heap,r).or(v)));".into(),
                        ("java/util/OptionalLong","orElse","(J)J") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let r=pop_r(&mut stack);stack.push(V::L(optional_long_or_else(heap,r,v)));".into(),
                        ("java/lang/String","getBytes","(Ljava/nio/charset/Charset;)[B") if self.multi_classes.is_some()=>"let cs=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(string_bytes_utf8(heap,r,cs))));".into(),
                        ("com/google/common/hash/HashCode","asBytes","()[B") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(hash_code_as_bytes(heap,r))));".into(),
                        ("java/util/Optional","orElseThrow","(Ljava/util/function/Supplier;)Ljava/lang/Object;") if self.multi_classes.is_some()=>{self.interface_call("java/util/function/Supplier","get","()Ljava/lang/Object;")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/Supplier"&&v.1=="get"&&v.2=="()Ljava/lang/Object;").ok_or("Supplier.get no registrada")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);let v=match optional_value(heap,r){{Some(v)=>v,None=>{{let _opaque=call_guard(\"<jdk-callback>\");let ex=interface_dispatch_{id}(heap,f);throw_ref(heap,ex)}}}};stack.push(V::R(Some(v)));")},
                        ("java/lang/Long","longValue","()J") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::L(long_value(heap,r)));".into(),
                        ("java/lang/Long","intValue","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(long_int_value(heap,r)));".into(),
                        ("java/util/concurrent/atomic/AtomicBoolean","get","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(atomic_boolean_get(heap,r) as i32));".into(),
                        ("java/util/concurrent/atomic/AtomicBoolean","set","(Z)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);atomic_boolean_set(heap,r,v!=0);".into(),
                        ("java/util/concurrent/atomic/AtomicBoolean","compareAndSet","(ZZ)Z") if self.multi_classes.is_some()=>"let update=pop_i(&mut stack);let expect=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(atomic_boolean_compare_and_set(heap,r,expect!=0,update!=0) as i32));".into(),
                        ("java/util/concurrent/atomic/AtomicBoolean","weakCompareAndSet","(ZZ)Z") if self.multi_classes.is_some()=>"let update=pop_i(&mut stack);let expect=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(atomic_boolean_compare_and_set(heap,r,expect!=0,update!=0) as i32));".into(),
                        ("java/util/concurrent/atomic/AtomicBoolean","getAndSet","(Z)Z") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);let old=atomic_boolean_get_and_set(heap,r,v!=0);stack.push(V::I(old as i32));".into(),
                        ("java/lang/Integer","intValue","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(integer_value(heap,r)));".into(),
                        ("java/lang/Byte","byteValue","()B") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(byte_value(heap,r)));".into(),
                        ("java/lang/Boolean","booleanValue","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(boolean_value(heap,r) as i32));".into(),
                        ("java/lang/ThreadLocal"|"java/lang/InheritableThreadLocal","get","()Ljava/lang/Object;") if self.multi_classes.is_some()=>self.threadlocal_get_call()?,
                        ("java/lang/ThreadLocal"|"java/lang/InheritableThreadLocal","set","(Ljava/lang/Object;)V") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);threadlocal_set(heap,r,v);".into(),
                        ("java/lang/ThreadLocal"|"java/lang/InheritableThreadLocal","remove","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);threadlocal_remove(heap,r);".into(),
                        ("java/util/concurrent/TimeUnit","ordinal","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);timeunit_id(heap,r);stack.push(V::I(enum_ordinal(heap,r)));".into(),
                        ("java/util/concurrent/TimeUnit","name","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);timeunit_id(heap,r);stack.push(V::R(enum_name(heap,r)));".into(),
                        ("java/nio/file/spi/FileSystemProvider","getScheme","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(zip_fs_provider_get_scheme(heap,r))));".into(),
                        ("java/util/concurrent/TimeUnit","convert","(JLjava/util/concurrent/TimeUnit;)J") if self.multi_classes.is_some()=>"let source=pop_r(&mut stack);let value=pop_l(&mut stack);let r=pop_r(&mut stack);stack.push(V::L(timeunit_convert(heap,r,value,source)));".into(),
                        ("java/util/concurrent/TimeUnit","toNanos"|"toMicros"|"toMillis"|"toSeconds"|"toMinutes"|"toHours"|"toDays","(J)J") if self.multi_classes.is_some()=>{let target=match name{"toNanos"=>0,"toMicros"=>1,"toMillis"=>2,"toSeconds"=>3,"toMinutes"=>4,"toHours"=>5,_=>6};format!("let value=pop_l(&mut stack);let r=pop_r(&mut stack);stack.push(V::L(timeunit_to(heap,r,value,{target}))); ")},
                        ("java/lang/Enum","ordinal","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(enum_ordinal(heap,r)));".into(),
                        ("java/lang/Enum","name","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(enum_name(heap,r)));".into(),
                        _ if self.multi_classes.is_some() && project_class(owner) && matches!((name,desc),("ordinal","()I")|("name","()Ljava/lang/String;")) && {let id=self.ensure_multi_class(owner)?;self.multi_classes.as_ref().unwrap()[id].enum_class}=>{
                            if name=="ordinal" {"let r=pop_r(&mut stack);stack.push(V::I(enum_ordinal(heap,r)));".into()} else {"let r=pop_r(&mut stack);stack.push(V::R(enum_name(heap,r)));".into()}
                        },
                        _ if self.multi_classes.is_some() && owner.starts_with('[') && name=="clone" && desc=="()Ljava/lang/Object;" => "let r=pop_r(&mut stack);stack.push(V::R(Some(ref_array_clone(heap,r))));".into(),
                        ("java/lang/StringBuilder","capacity","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(builder_capacity(heap,r)));".into(),
                        ("java/lang/StringBuilder","setLength","(I)V") if self.multi_classes.is_some()=>"let n=pop_i(&mut stack);let r=pop_r(&mut stack);builder_set_length(heap,r,n);".into(),
                        ("java/lang/StringBuilder","trimToSize","()V") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);builder_trim(heap,r);".into(),
                        ("java/lang/ClassLoader","getParent","()Ljava/lang/ClassLoader;") if self.multi_classes.is_some()=>{
                            if std::env::var_os("MC_AOT_STANDARD_SYSTEM_LOADER").as_deref()!=Some(std::ffi::OsStr::new("1")){return Err("ClassLoader.getParent: requiere MC_AOT_STANDARD_SYSTEM_LOADER=1".into());}
                            "let r=pop_r(&mut stack);stack.push(V::R(classloader_parent(heap,r)));".into()
                        },
                        ("java/lang/StringBuilder","append","(Ljava/lang/Object;)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(builder_append_object(heap,r,v)));".into(),
                        ("java/lang/StringBuilder","append","(Ljava/lang/CharSequence;II)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let end=pop_i(&mut stack);let start=pop_i(&mut stack);let v=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(builder_append_charsequence_range(heap,r,v,start,end)));".into(),
                        ("java/lang/StringBuilder","append","(Ljava/lang/CharSequence;)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(builder_append_charsequence(heap,r,v)));".into(),
                        ("java/lang/StringBuilder","append","(Ljava/lang/String;)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(builder_append_string(heap,r,v)));".into(),
                        ("java/lang/StringBuilder","append","(C)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(builder_append(heap,r,&[v as u16])));".into(),
                        ("java/lang/StringBuilder","append","(I)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);let text:Vec<u16>=v.to_string().encode_utf16().collect();stack.push(V::R(builder_append(heap,r,&text)));".into(),
                        ("java/lang/StringBuilder","append","(J)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_l(&mut stack);let r=pop_r(&mut stack);let text:Vec<u16>=v.to_string().encode_utf16().collect();stack.push(V::R(builder_append(heap,r,&text)));".into(),
                        ("java/lang/StringBuilder","append","(Z)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);let text:Vec<u16>=(if (v&1)!=0 {\"true\"}else{\"false\"}).encode_utf16().collect();stack.push(V::R(builder_append(heap,r,&text)));".into(),
                        ("java/lang/StringBuilder","length","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(builder_len(heap,r)));".into(),
                        ("java/lang/Object","equals","(Ljava/lang/Object;)Z") if self.multi_classes.is_some()=>"let other=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(object_equals_guard(heap,r,other) as i32));".into(),
                        ("java/lang/Object","toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let s=object_to_string_guard(heap,r);stack.push(V::R(Some(s)));".into(),
                        ("java/lang/StringBuilder","append","(D)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>r#"error("StringBuilder.append(double): representación decimal no implementada");"#.into(),
                        ("java/lang/StringBuilder","append","(F)Ljava/lang/StringBuilder;") if self.multi_classes.is_some()=>r#"error("StringBuilder.append(float): representación decimal no implementada");"#.into(),
                        ("java/lang/Integer","highestOneBit","(I)I") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);stack.push(V::I(integer_highest_one_bit(v)));".into(),
                        ("java/lang/StringBuilder","toString","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(builder_to_string(heap,r))));".into(),
                        ("java/util/ArrayList","stream","()Ljava/util/stream/Stream;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(collection_stream(heap,r))));".into(),
                        ("java/util/ServiceLoader","iterator","()Ljava/util/Iterator;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(service_iterator(heap,r))));".into(),
                        ("java/lang/Class","getModule","()Ljava/lang/Module;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(class_module(heap,r))));".into(),
                        ("java/lang/Class","getTypeParameters","()[Ljava/lang/reflect/TypeVariable;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let _=array_id(heap,r);error(\"Class.getTypeParameters: reflexión de genéricos no modelada en el perfil (gson TypeToken.getParameterized compilable, pero trampa en tiempo de ejecución)\");stack.push(V::R(None));".into(),
                        ("java/lang/Module","getLayer","()Ljava/lang/ModuleLayer;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(module_layer(heap,r))));".into(),
                        ("java/lang/ModuleLayer","findModule","(Ljava/lang/String;)Ljava/util/Optional;") if self.multi_classes.is_some()=>"let name=pop_r(&mut stack);let layer=pop_r(&mut stack);let module=find_jfr_module(heap,layer,name);stack.push(V::R(Some(optional_new(heap,module))));".into(),
                        ("java/lang/Class","getCanonicalName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let s=class_canonical_top(heap,r);stack.push(V::R(Some(s)));".into(),
                        ("java/lang/Class","getEnumConstants","()[Ljava/lang/Object;") if self.multi_classes.is_some()=>{self.uses_enum_constants=true;"let r=pop_r(&mut stack);stack.push(V::R(enum_constants(heap,r)));".into()},
                        ("java/lang/Class","getSimpleName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(class_simple_name(heap,r))));".into(),
                        ("java/lang/Class","getName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(class_get_name(heap,r))));".into(),
                        _ if self.multi_classes.is_some() && name=="getClass" && desc=="()Ljava/lang/Class;" && (owner=="java/lang/Object" || project_class(owner) || matches!(owner,"java/lang/String"|"java/lang/StringBuilder"))=>"let r=pop_r(&mut stack);stack.push(V::R(Some(object_get_class(heap,r))));".into(),
                        ("java/lang/Class","desiredAssertionStatus","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(class_assertion_status(heap,r) as i32));".into(),
                        ("java/lang/Class","getModifiers","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(class_modifiers(heap,r,PROJECT_CLASS_MODIFIERS)));".into(),
                        ("java/lang/Class","isArray","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(class_is_array(heap,r) as i32));".into(),
                        ("java/lang/Class","getComponentType","()Ljava/lang/Class;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(class_component_type(heap,r)));".into(),
                        ("java/lang/Class","getDeclaringClass","()Ljava/lang/Class;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(class_declaring_class(heap,r)));".into(),
                        ("java/lang/Class","isPrimitive","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(class_is_primitive(heap,r) as i32));".into(),
                        ("java/lang/Class","asSubclass","(Ljava/lang/Class;)Ljava/lang/Class;") if self.multi_classes.is_some()=>"let target=pop_r(&mut stack);let this=pop_r(&mut stack);stack.push(V::R(Some(class_as_subclass(heap,this,target,PROJECT_INTERFACES,PROJECT_TYPES,PROJECT_INTERFACE_CLASSES))));".into(),
                        ("java/lang/Class","isAssignableFrom","(Ljava/lang/Class;)Z") if self.multi_classes.is_some()=>"let other=pop_r(&mut stack);let this=pop_r(&mut stack);stack.push(V::I(class_assignable(heap,this,other,PROJECT_INTERFACES,PROJECT_TYPES) as i32));".into(),
                        ("java/lang/Class","getMethod","(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;") if self.multi_classes.is_some()=>"let args=pop_r(&mut stack);let name=pop_r(&mut stack);let class=pop_r(&mut stack);stack.push(V::R(Some(reflect_get_method(heap,class,name,args,REFLECT_METHODS))));".into(),
                        ("java/lang/reflect/AccessibleObject"|"java/lang/reflect/Constructor"|"java/lang/reflect/Method","isAccessible","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(accessible_is_accessible(heap,r) as i32));".into(),
                        ("java/lang/reflect/AccessibleObject"|"java/lang/reflect/Constructor"|"java/lang/reflect/Method","setAccessible","(Z)V") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);accessible_set(heap,r,v);".into(),
                        ("java/lang/reflect/Constructor"|"java/lang/reflect/Method","getModifiers","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(member_modifiers(heap,r,REFLECT_CTOR_MODIFIERS,REFLECT_METHOD_MODIFIERS)));".into(),
                        ("java/lang/reflect/Constructor"|"java/lang/reflect/Method","getDeclaringClass","()Ljava/lang/Class;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(member_declaring_class(heap,r,REFLECT_METHODS))));".into(),
                        ("java/lang/reflect/Method","invoke","(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let args=pop_r(&mut stack);let receiver=pop_r(&mut stack);let method=pop_r(&mut stack);stack.push(V::R(reflect_invoke(heap,method,receiver,args)));".into(),
                        ("java/lang/Class","getDeclaredConstructor","([Ljava/lang/Class;)Ljava/lang/reflect/Constructor;") if self.multi_classes.is_some()=>"let args=pop_r(&mut stack);let class=pop_r(&mut stack);stack.push(V::R(Some(reflect_get_declared_constructor(heap,class,args,REFLECT_DECLARED_CTORS))));".into(),
                        ("java/lang/Class","getConstructor","([Ljava/lang/Class;)Ljava/lang/reflect/Constructor;") if self.multi_classes.is_some()=>"let args=pop_r(&mut stack);let class=pop_r(&mut stack);stack.push(V::R(Some(reflect_get_constructor(heap,class,args,REFLECT_CTORS))));".into(),
                        ("java/lang/reflect/Constructor","newInstance","([Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let args=pop_r(&mut stack);let ctor=pop_r(&mut stack);stack.push(V::R(reflect_construct(heap,ctor,args)));".into(),
                        ("java/util/ServiceConfigurationError","getMessage","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(service_error_message(heap,r)));".into(),
                        (_,"addSuppressed","(Ljava/lang/Throwable;)V") if self.multi_classes.is_some() && (owner=="java/lang/Throwable" || known_exception(owner).is_some())=>"let suppressed=pop_r(&mut stack);let r=pop_r(&mut stack);exception_add_suppressed(heap,r,suppressed);".into(),
                        (_,"printStackTrace","(Ljava/io/PrintStream;)V") if self.multi_classes.is_some() && (known_exception(owner).is_some() || (project_class(owner) && self.resolve_exception_type(owner).is_ok()))=>"let stream=pop_r(&mut stack);let exception=pop_r(&mut stack);print_stack_trace_guard(heap,exception,stream);".into(),
                        ("java/net/URISyntaxException","getInput"|"getReason","()Ljava/lang/String;") if self.multi_classes.is_some()=>format!("let r=pop_r(&mut stack);stack.push(V::R(Some(uri_syntax_part(heap,r,{}))));",name=="getInput"),
                        ("java/net/URISyntaxException","getIndex","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(uri_syntax_index(heap,r)));".into(),
                        (_,"getMessage","()Ljava/lang/String;") if self.multi_classes.is_some() && (known_exception(owner).is_some() || (project_class(owner) && self.resolve_exception_type(owner).is_ok()))=>"let r=pop_r(&mut stack);stack.push(V::R(exception_message(heap,r)));".into(),
                        (_,"getCause","()Ljava/lang/Throwable;") if self.multi_classes.is_some() && (known_exception(owner).is_some() || (project_class(owner) && self.resolve_exception_type(owner).is_ok()))=>"let r=pop_r(&mut stack);stack.push(V::R(invocation_cause(heap,r)));".into(),
                        ("java/lang/reflect/InvocationTargetException","getTargetException","()Ljava/lang/Throwable;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(invocation_cause(heap,r)));".into(),
                        ("java/lang/ClassLoader","getResources","(Ljava/lang/String;)Ljava/util/Enumeration;") if self.multi_classes.is_some()=>{self.uses_resource_lookup=true;"let name=pop_r(&mut stack);let loader=pop_r(&mut stack);stack.push(V::R(Some(classloader_resources(heap,loader,name,STATIC_BINDER_PRESENT,LOG4J_PROVIDER_ABSENT))));".into()},
                        ("java/lang/ClassLoader","loadClass","(Ljava/lang/String;)Ljava/lang/Class;") if self.multi_classes.is_some()=>"let name=pop_r(&mut stack);let loader=pop_r(&mut stack);stack.push(V::R(Some(classloader_load(heap,loader,name,PRECOMPILED_CLASSES))));".into(),
                        ("java/lang/Class","getClassLoader","()Ljava/lang/ClassLoader;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(class_get_loader(heap,r)));".into(),
                        ("java/lang/String","toUpperCase","(Ljava/util/Locale;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let locale=pop_r(&mut stack);let r=pop_r(&mut stack);let s=string_upper_root_ascii(heap,r,locale);stack.push(V::R(Some(s)));".into(),
                        ("java/lang/String","toLowerCase","(Ljava/util/Locale;)Ljava/lang/String;") if self.multi_classes.is_some()=>"let locale=pop_r(&mut stack);let r=pop_r(&mut stack);let s=string_lower_root_ascii(heap,r,locale);stack.push(V::R(Some(s)));".into(),
                        ("java/lang/String","toLowerCase","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(string_lower_ascii(heap,r))));".into(),
                        ("java/lang/String","trim","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(string_trim(heap,r))));".into(),
                        ("java/lang/String","hashCode","()I")=>"let r=pop_r(&mut stack);stack.push(V::I(string_hash(heap,r)));".into(),
                        ("java/lang/String","getChars","(II[CI)V") if self.multi_classes.is_some()=>"let off=pop_i(&mut stack);let dst=pop_r(&mut stack);let end=pop_i(&mut stack);let begin=pop_i(&mut stack);let r=pop_r(&mut stack);string_get_chars(heap,r,begin,end,dst,off);".into(),
                        ("java/lang/String","substring","(II)Ljava/lang/String;") if self.multi_classes.is_some()=>"let end=pop_i(&mut stack);let begin=pop_i(&mut stack);let s=pop_r(&mut stack);let x=string_substring(heap,s,begin,Some(end));stack.push(V::R(Some(x)));".into(),
                        ("java/lang/String","substring","(I)Ljava/lang/String;") if self.multi_classes.is_some()=>"let begin=pop_i(&mut stack);let s=pop_r(&mut stack);let x=string_substring(heap,s,begin,None);stack.push(V::R(Some(x)));".into(),
                        ("java/lang/String","length","()I")=>"let a=pop_r(&mut stack); stack.push(V::I(string_len(heap,a)));".into(),
                        ("java/lang/String","equalsIgnoreCase","(Ljava/lang/String;)Z")=>"let b=pop_r(&mut stack);let a=pop_r(&mut stack);stack.push(V::I(string_equals_ignore_case(heap,a,b) as i32));".into(),
                        ("java/lang/String","isEmpty","()Z")=>"let a=pop_r(&mut stack); stack.push(V::I((string_len(heap,a)==0) as i32));".into(),
                        ("java/lang/String","charAt","(I)C")=>"let i=pop_i(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_char_at(heap,a,i)));".into(),
                        ("java/lang/String","equals","(Ljava/lang/Object;)Z")=>"let b=pop_r(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_equals(heap,a,b) as i32));".into(),
                        ("java/lang/String","startsWith","(Ljava/lang/String;)Z")=>"let b=pop_r(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_starts(heap,a,b) as i32));".into(),
                        ("java/lang/String","endsWith","(Ljava/lang/String;)Z")=>"let b=pop_r(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_ends(heap,a,b) as i32));".into(),
                        ("java/lang/String","indexOf","(I)I")=>"let c=pop_i(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_index_char(heap,a,c,0)));".into(),
                        ("java/lang/String","indexOf","(II)I")=>"let from=pop_i(&mut stack); let c=pop_i(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_index_char(heap,a,c,from)));".into(),
                        ("java/lang/String","split","(Ljava/lang/String;I)[Ljava/lang/String;") if self.multi_classes.is_some()=>"let limit=pop_i(&mut stack);let pattern=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(string_split_version(heap,r,pattern,limit))));".into(),
                        ("java/lang/String","split","(Ljava/lang/String;)[Ljava/lang/String;") if self.multi_classes.is_some()=>"let regex=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(string_split_literal(heap,r,regex))));".into(),
                        ("java/lang/String","toCharArray","()[C") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(string_to_char_array(heap,r))));".into(),
                        ("java/lang/String","contains","(Ljava/lang/CharSequence;)Z") if self.multi_classes.is_some()=>"let q=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(string_contains_sequence(heap,r,q) as i32));".into(),
                        ("java/lang/String","lastIndexOf","(Ljava/lang/String;)I")=>"let b=pop_r(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_last_index_str(heap,a,b)));".into(),
                        ("java/lang/String","lastIndexOf","(I)I") if self.multi_classes.is_some()=>"let c=pop_i(&mut stack);let a=pop_r(&mut stack);stack.push(V::I(string_last_index_char(heap,a,c,2147483647)));".into(),
                        ("java/lang/String","lastIndexOf","(II)I") if self.multi_classes.is_some()=>"let from=pop_i(&mut stack);let c=pop_i(&mut stack);let a=pop_r(&mut stack);stack.push(V::I(string_last_index_char(heap,a,c,from)));".into(),
                        ("java/lang/String","indexOf","(Ljava/lang/String;)I")=>"let b=pop_r(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_index_str(heap,a,b,0)));".into(),
                        ("java/lang/String","indexOf","(Ljava/lang/String;I)I")=>"let from=pop_i(&mut stack); let b=pop_r(&mut stack); let a=pop_r(&mut stack); stack.push(V::I(string_index_str(heap,a,b,from)));".into(),
                        ("java/io/PrintStream","println","(Ljava/lang/String;)V") if self.static_fields.is_none()=>"let s=pop_r(&mut stack); let out=pop_r(&mut stack); print_string_line(heap,out,s);".into(),
                        ("java/io/PrintStream","println","(I)V") if self.static_fields.is_none()=>"let v=pop_i(&mut stack); let out=pop_r(&mut stack); print_line(heap,out,&v.to_string());".into(),
                        ("java/io/PrintStream","println","(J)V") if self.static_fields.is_none()=>"let v=pop_l(&mut stack); let out=pop_r(&mut stack); print_line(heap,out,&v.to_string());".into(),
                        ("java/io/PrintStream","println","(Z)V") if self.static_fields.is_none()=>"let v=pop_i(&mut stack); let out=pop_r(&mut stack); print_line(heap,out,if (v&1)!=0 {\"true\"} else {\"false\"});".into(),
                        ("java/io/PrintStream","println","()V") if self.static_fields.is_none()=>"let out=pop_r(&mut stack); print_line(heap,out,\"\");".into(),
                        _ if self.multi_classes.is_some() && matches!(owner,"java/util/HashMap"|"java/util/concurrent/ConcurrentHashMap"|"java/util/concurrent/ConcurrentMap"|"java/util/Map") && name=="computeIfAbsent" && desc=="(Ljava/lang/Object;Ljava/util/function/Function;)Ljava/lang/Object;"=>self.map_compute_if_absent()?,
                        _ if self.multi_classes.is_some() && collection_intrinsic(owner,name,desc).is_some()=>collection_intrinsic(owner,name,desc).unwrap().into(),
                        ("java/lang/Object","hashCode","()I") if self.multi_classes.is_some()=>{let id=self.register_object_hashcode();format!("let r=pop_r(&mut stack);stack.push(V::I(virtual_dispatch_{id}(heap,r)));").into()},
("java/util/logging/Logger","log","(Ljava/util/logging/Level;Ljava/lang/String;Ljava/lang/Throwable;)V") if self.multi_classes.is_some()=>"let th=pop_r(&mut stack);let msg=pop_r(&mut stack);let level=pop_r(&mut stack);let r=pop_r(&mut stack);logger_log(heap,level,msg,th);".into(),
_ if self.multi_classes.is_some() && project_class(owner)=>self.virtual_call(owner,name,desc)?,
                        ("java/lang/ScopedValue","isBound","()Z") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::I(scoped_value_is_bound(heap,r) as i32));".into(),
                        ("java/lang/ScopedValue","get","()Ljava/lang/Object;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(scoped_value_get(heap,r)));".into(),
                        ("java/lang/ScopedValue$Carrier","run","(Ljava/lang/Runnable;)V") if self.multi_classes.is_some()=>{self.interface_call("java/lang/Runnable","run","()V")?;let id=self.interface_calls.iter().position(|v|v.0=="java/lang/Runnable"&&v.1=="run"&&v.2=="()V").ok_or("Runnable.run no registrada")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);scoped_carrier_run(heap,r,f,interface_dispatch_{id});").into()},
                        ("java/lang/Thread","getStackTrace","()[Ljava/lang/StackTraceElement;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let _=r;error(\"Thread.getStackTrace: no soportado en el perfil AOT (solo la rama isDebugEnabled lo alcanza)\")".into(),
                        ("java/lang/Throwable","setStackTrace","([Ljava/lang/StackTraceElement;)V") if self.multi_classes.is_some()=>"let t=pop_r(&mut stack);let r=pop_r(&mut stack);exception_set_stack_trace(heap,r,t);".into(),
                        ("java/lang/Throwable","getStackTrace","()[Ljava/lang/StackTraceElement;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(exception_get_stack_trace(heap,r))));".into(),
                        ("java/lang/StackTraceElement","getClassName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let _=r;error(\"StackTraceElement.getClassName: no soportado en el perfil AOT (rama debug)\")".into(),
                        ("java/lang/StackTraceElement","getMethodName","()Ljava/lang/String;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let _=r;error(\"StackTraceElement.getMethodName: no soportado en el perfil AOT (rama debug)\")".into(),
                        ("java/lang/StackTraceElement","getLineNumber","()I") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);let _=r;error(\"StackTraceElement.getLineNumber: no soportado en el perfil AOT (rama debug)\")".into(),
                        ("java/util/EnumMap","put","(Ljava/lang/Enum;Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"let value=pop_r(&mut stack);let key=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(enum_map_put(heap,r,key,value)));".into(),
                        ("java/util/HexFormat","withUpperCase","()Ljava/util/HexFormat;") if self.multi_classes.is_some()=>"let r=pop_r(&mut stack);stack.push(V::R(Some(hex_format_with_upper_case(heap,r))));".into(),
                        ("java/util/HexFormat","toHexDigits","(B)Ljava/lang/String;") if self.multi_classes.is_some()=>"let v=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(hex_digits_byte(heap,r,v))));".into(),
                        _=>return Err(format!("invokevirtual no soportado: {owner}.{name}{desc}")),
                    }
                },
                0xb7 => {
                    let idx=u16::from_be_bytes([read()?,read()?]);let (owner,method,desc)=method_ref(&m.cp,idx)?;
                    if method!="<init>" {
                        if self.multi_classes.is_some() && (owner,method,desc)==("java/lang/SecurityManager","getClassContext","()[Ljava/lang/Class;"){"let r=pop_r(&mut stack);array_id(heap,r);error(\"SecurityManager.getClassContext: pila JDK no modelada\");".into()}
                        else if self.multi_classes.is_some() && project_class(owner){self.special_call(class,owner,method,desc)?}
                        else{return Err(format!("invokespecial no soportado: {owner}.{method}{desc}"));}
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/SecurityManager","()V") {
                        "let r=pop_r(&mut stack);check_any_object(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/CopyOnWriteArrayList","()V") {r#"error("CopyOnWriteArrayList: concurrencia no implementada");"#.into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/WeakHashMap","()V") {"error(\"WeakHashMap(): semántica de claves débiles no implementada\");".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/text/SimpleDateFormat","(Ljava/lang/String;)V") {"error(\"SimpleDateFormat(String): no soportado\");".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/text/SimpleDateFormat","(Ljava/lang/String;Ljava/util/Locale;)V") {"error(\"SimpleDateFormat(String, Locale): no soportado (ruta de reporte de fallos; no ejecutada en el boot)\");".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/FileOutputStream","(Ljava/lang/String;)V") {"error(\"FileOutputStream(String): no soportado\");".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/PrintStream","(Ljava/io/OutputStream;)V") {"error(\"PrintStream(OutputStream): no soportado\");".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/PrintStream","(Ljava/io/OutputStream;ZLjava/nio/charset/Charset;)V") {"let charset=pop_r(&mut stack);let _auto=pop_i(&mut stack);let out=pop_r(&mut stack);let r=pop_r(&mut stack);check_any_object(heap,r);check_any_object(heap,out);let _=charset;".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/ref/WeakReference","(Ljava/lang/Object;)V") {"let value=pop_r(&mut stack);let r=pop_r(&mut stack);weak_loader_set(heap,r,value);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/RuntimePermission","(Ljava/lang/String;)V") {"let name=pop_r(&mut stack);let r=pop_r(&mut stack);runtime_permission_init(heap,r,name);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/Properties","()V") {"let r=pop_r(&mut stack);java_properties_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/File","(Ljava/lang/String;)V") {"let s=pop_r(&mut stack);let r=pop_r(&mut stack);file_init(heap,r,s);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/StackTraceElement","(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;I)V") {"let line=pop_i(&mut stack);let file=pop_r(&mut stack);let method=pop_r(&mut stack);let declaring=pop_r(&mut stack);let r=pop_r(&mut stack);stack_element_init(heap,r,declaring,method,file,line);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/File","(Ljava/io/File;Ljava/lang/String;)V") {"let child=pop_r(&mut stack);let parent=pop_r(&mut stack);let r=pop_r(&mut stack);file_init_child(heap,r,parent,child);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/FileInputStream","(Ljava/io/File;)V") {"let f=pop_r(&mut stack);let r=pop_r(&mut stack);file_input_init_from_file(heap,r,f);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/FileInputStream","(Ljava/lang/String;)V") {"let s=pop_r(&mut stack);let r=pop_r(&mut stack);file_input_init_from_text(heap,r,s);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/FileInputStream","(Ljava/nio/file/Path;)V") {"let p=pop_r(&mut stack);let r=pop_r(&mut stack);file_input_init_from_path(heap,r,p);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/locks/ReentrantReadWriteLock","(Z)V") {"let _fair=pop_i(&mut stack);let r=pop_r(&mut stack);rw_lock_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/locks/ReentrantReadWriteLock","()V") {"let r=pop_r(&mut stack);rw_lock_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/locks/ReentrantLock","()V") {"let r=pop_r(&mut stack);reentrant_count(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/ForkJoinPool","(ILjava/util/concurrent/ForkJoinPool$ForkJoinWorkerThreadFactory;Ljava/lang/Thread$UncaughtExceptionHandler;Z)V") {"let handler=pop_r(&mut stack);let factory=pop_r(&mut stack);let async_mode=pop_i(&mut stack);let parallelism=pop_i(&mut stack);let r=pop_r(&mut stack);forkjoin_pool_init(heap,r,parallelism,factory,handler,async_mode);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/UUID","(JJ)V") {"let least=pop_l(&mut stack);let most=pop_l(&mut stack);let r=pop_r(&mut stack);uuid_init(heap,r,most,least);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/BitSet","(I)V") {"let n=pop_i(&mut stack);let r=pop_r(&mut stack);bitset_init_checked(heap,r,n);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/BitSet","()V") {"let r=pop_r(&mut stack);let r=r;".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicInteger","()V") {"let r=pop_r(&mut stack);atomic_integer_set(heap,r,0);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicBoolean","()V") {"let r=pop_r(&mut stack);atomic_boolean_set(heap,r,false);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicBoolean","(Z)V") {"let v=pop_i(&mut stack);let r=pop_r(&mut stack);atomic_boolean_set(heap,r,v!=0);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicInteger","(I)V") {"let v=pop_i(&mut stack);let r=pop_r(&mut stack);atomic_integer_set(heap,r,v);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicLong","()V") {"let r=pop_r(&mut stack);atomic_long_set(heap,r,0);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicLong","(J)V") {"let v=pop_l(&mut stack);let r=pop_r(&mut stack);atomic_long_set(heap,r,v);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicReference","()V") {
                        "let r=pop_r(&mut stack);atomic_ref_set(heap,r,None);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/atomic/AtomicReference","(Ljava/lang/Object;)V") {
                        "let v=pop_r(&mut stack);let r=pop_r(&mut stack);atomic_ref_set(heap,r,v);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/LinkedHashSet","(I)V") {"let n=pop_i(&mut stack);let r=pop_r(&mut stack);linked_set_capacity(heap,r,n);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/ArrayList","(I)V") {
                        "let n=pop_i(&mut stack);let r=pop_r(&mut stack);list_construct_capacity(heap,r,n);".into()
                    } else                     if self.multi_classes.is_some() && (owner,desc)==("java/util/ArrayList","(Ljava/util/Collection;)V") {
                        "let values=pop_r(&mut stack);let r=pop_r(&mut stack);list_construct_collection(heap,r,values);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/LinkedHashMap","()V") {"let r=pop_r(&mut stack);linked_map_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/TreeMap","()V") {"let r=pop_r(&mut stack);tree_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/String","([C)V") {"let chars=pop_r(&mut stack);let r=pop_r(&mut stack);string_init_chars(heap,r,chars);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/IdentityHashMap","()V") {"let r=pop_r(&mut stack);identity_map_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/HashMap","(I)V") {"let n=pop_i(&mut stack);let r=pop_r(&mut stack);hashmap_init_capacity(heap,r,n);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/HashMap","()V") {"let r=pop_r(&mut stack);hashmap_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/text/DecimalFormat","(Ljava/lang/String;Ljava/text/DecimalFormatSymbols;)V") {"let symbols=pop_r(&mut stack);let pattern=pop_r(&mut stack);let r=pop_r(&mut stack);decimal_format_init(heap,r,pattern,symbols);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/HashMap","(Ljava/util/Map;)V") {"let source=pop_r(&mut stack);let r=pop_r(&mut stack);hashmap_init_map(heap,r,source);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/ByteArrayInputStream","([B)V") {"let b=pop_r(&mut stack);let r=pop_r(&mut stack);byte_input_init(heap,r,b);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/InputStreamReader","(Ljava/io/InputStream;Ljava/nio/charset/Charset;)V") {"let charset=pop_r(&mut stack);let stream=pop_r(&mut stack);let r=pop_r(&mut stack);reader_init(heap,r,stream,charset);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/StringReader","(Ljava/lang/String;)V") {"let v=pop_r(&mut stack);let r=pop_r(&mut stack);string_reader_init(heap,r,v);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/zip/GZIPOutputStream","(Ljava/io/OutputStream;)V") {"let stream=pop_r(&mut stack);let r=pop_r(&mut stack);gzip_out_init(heap,r,stream);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/zip/GZIPInputStream","(Ljava/io/InputStream;)V") {"let stream=pop_r(&mut stack);let r=pop_r(&mut stack);gzip_in_init(heap,r,stream);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/zip/DeflaterOutputStream","(Ljava/io/OutputStream;)V") {"let stream=pop_r(&mut stack);let r=pop_r(&mut stack);deflate_out_init(heap,r,stream);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/zip/InflaterInputStream","(Ljava/io/InputStream;)V") {"let stream=pop_r(&mut stack);let r=pop_r(&mut stack);deflate_in_init(heap,r,stream);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/io/BufferedOutputStream","(Ljava/io/OutputStream;)V") {"let stream=pop_r(&mut stack);let r=pop_r(&mut stack);buffered_output_init(heap,r,stream);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/concurrent/CompletableFuture","()V") {
                        if !futures_optin()? {return Err("CompletableFuture: requiere MC_AOT_FUTURES=restricted".into());}
                        "let r=pop_r(&mut stack);pending_future_init(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/net/URL","(Ljava/lang/String;)V") {"let v=pop_r(&mut stack);let r=pop_r(&mut stack);url_init(heap,r,v);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("com/google/gson/GsonBuilder","()V") {"let r=pop_r(&mut stack);gson_builder_init(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/Date","()V") {"let r=pop_r(&mut stack);let now=clock_millis();date_set(heap,r,now);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/Date","(J)V") {"let v=pop_l(&mut stack);let r=pop_r(&mut stack);date_set(heap,r,v);".into()
                    } else                     if self.multi_classes.is_some() && (owner,desc)==("java/lang/StringBuilder","()V") {
                        "let r=pop_r(&mut stack);builder_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/StringBuilder","(I)V") {"let capacity=pop_i(&mut stack);let r=pop_r(&mut stack);builder_init_capacity(heap,r,capacity);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/lang/StringBuilder","(Ljava/lang/String;)V") {
                        "let v=pop_r(&mut stack);let r=pop_r(&mut stack);builder_init_string(heap,r,v);".into()
                    } else                     if self.multi_classes.is_some() && (owner,desc)==("java/lang/Enum","(Ljava/lang/String;I)V") {
                        "let ordinal=pop_i(&mut stack);let name=pop_r(&mut stack);let r=pop_r(&mut stack);enum_init(heap,r,name,ordinal);".into()
                    } else                     if self.multi_classes.is_some() && matches!((owner,desc),("java/lang/ThreadLocal"|"java/lang/InheritableThreadLocal","()V")) {
                        "let r=pop_r(&mut stack);threadlocal_id(heap,r);".into()
                    } else if self.multi_classes.is_some() && matches!(owner,"java/util/concurrent/ConcurrentHashMap"|"java/util/concurrent/LinkedBlockingQueue"|"java/util/concurrent/ConcurrentLinkedQueue"|"java/util/ArrayDeque"|"java/util/ArrayList"|"java/util/HashSet"|"java/util/LinkedHashSet"|"java/util/TreeSet") && desc=="()V" {
                        format!("let r=pop_r(&mut stack);collection_init(heap,r,{owner:?});")
                    } else if self.multi_classes.is_some() && matches!(owner,"java/util/concurrent/ConcurrentHashMap"|"java/util/ArrayDeque"|"java/util/ArrayList"|"java/util/HashSet"|"java/util/LinkedHashSet"|"java/util/TreeSet"|"java/util/ArrayDeque") && desc=="(I)V" {
                        format!("let cap=pop_i(&mut stack);let r=pop_r(&mut stack);let _=cap;collection_init(heap,r,{owner:?});")
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/Spliterators$AbstractSpliterator","(JI)V") {
                        "let flags=pop_i(&mut stack);let estimate=pop_l(&mut stack);let r=pop_r(&mut stack);spliterator_init(heap,r,estimate,flags);".into()
                    } else if self.multi_classes.is_some() && matches!((owner,desc),("java/lang/Object"|"java/lang/Record"|"java/lang/Number"|"java/util/AbstractCollection"|"java/util/AbstractList"|"java/util/AbstractSequentialList"|"java/util/AbstractMap"|"java/util/AbstractSet"|"java/util/concurrent/AbstractExecutorService","()V")) {
                        "let r=pop_r(&mut stack);check_any_object(heap,r);".into()
                    } else if owner=="net/minecraft/IdentifierException" && matches!(desc,"(Ljava/lang/String;)V"|"(Ljava/lang/String;Ljava/lang/Throwable;)V") && self.multi_classes.is_some() {
                        self.validate_exception_class(owner)?;
                        "error(\"IdentifierException: constructor con escapeJava no implementado\");".into()
                    } else if self.multi_classes.is_some() && owner=="java/net/URISyntaxException" && matches!(desc,"(Ljava/lang/String;Ljava/lang/String;)V"|"(Ljava/lang/String;Ljava/lang/String;I)V") {
                        if desc.ends_with(";I)V") {"let index=pop_i(&mut stack);let reason=pop_r(&mut stack);let input=pop_r(&mut stack);let r=pop_r(&mut stack);uri_syntax_init(heap,r,input,reason,index);".into()} else {"let reason=pop_r(&mut stack);let input=pop_r(&mut stack);let r=pop_r(&mut stack);uri_syntax_init(heap,r,input,reason,-1);".into()}
                    } else if known_exception(owner).is_some() || (project_class(owner) && self.resolve_exception_type(owner).is_ok()) {
                        self.validate_exception_ctor(owner,desc)?;
                        let kind=known_exception(owner).unwrap_or(owner);
                        match desc {
                            "()V"=>format!("let r=pop_r(&mut stack); init_exception(heap,r,{kind:?},None);"),
                            "(Ljava/lang/String;)V"=>format!("let msg=pop_r(&mut stack);let r=pop_r(&mut stack);init_exception(heap,r,{kind:?},msg);"),
                            "(Ljava/io/IOException;)V"=>format!("let cause=pop_r(&mut stack);let r=pop_r(&mut stack);init_exception_from_io_cause(heap,r,{kind:?},cause);"),
                            "(Ljava/lang/Throwable;)V"=>format!("let cause=pop_r(&mut stack);let r=pop_r(&mut stack);init_exception_from_cause(heap,r,{kind:?},cause);"),
                            "(Ljava/lang/String;Ljava/lang/Throwable;)V"=>format!("let cause=pop_r(&mut stack);let msg=pop_r(&mut stack);let r=pop_r(&mut stack);init_exception_cause(heap,r,{kind:?},msg,cause);"),

                            _=>return Err(format!("constructor de excepción no soportado: {owner}{desc}")),
                        }
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/EnumMap","(Ljava/util/Map;)V") {"let source=pop_r(&mut stack);let r=pop_r(&mut stack);enum_map_init_map(heap,r,source);".into()
                    } else if self.multi_classes.is_some() && (owner,desc)==("java/util/EnumMap","(Ljava/lang/Class;)V") {"let keyclass=pop_r(&mut stack);let r=pop_r(&mut stack);enum_map_init_class(heap,r,keyclass);".into()
                    } else if self.multi_classes.is_some() && project_class(owner) {self.instance_call(owner,method,desc)?}
                    else {return Err(format!("constructor no soportado: {owner}.{method}{desc}"));}
                },
                0xb8 => {
                    let idx=u16::from_be_bytes([read()?,read()?]);let (callee,method,desc)=method_ref(&m.cp,idx)?;
                    if method.starts_with('<') {return Err("invocación explícita de inicializador no soportada".into());}
                    let call_sig=signature_ext(desc,self.multi_classes.is_some())?;
                    let mut pre=String::new();
                    for (i,t) in call_sig.args.iter().enumerate().rev() {pre.push_str(&format!("let x{i}={}(&mut stack); ",pop(*t)));}
                    let args=(0..call_sig.args.len()).map(|i|format!("x{i}")).collect::<Vec<_>>().join(",");
                    let expr=match (callee,method,desc) {
                        ("java/lang/Integer","highestOneBit","(I)I") if self.multi_classes.is_some()=>"stack.push(V::I(integer_highest_one_bit(x0)));".into(),
                        ("org/apache/logging/log4j/util/OsgiServiceLocator","loadServices","(Ljava/lang/Class;Ljava/lang/Class;Lorg/apache/logging/log4j/Logger;)Ljava/util/stream/Stream;") if self.multi_classes.is_some() && start==55 && self.active.last().is_some_and(|k| k=="org/apache/logging/log4j/util/ServiceLoaderUtil.safeStream(Ljava/lang/Class;Ljava/util/ServiceLoader;Lorg/apache/logging/log4j/Logger;)Ljava/util/stream/Stream;")=>{self.verify_log4j_absent_osgi()?;"{ error(\"Log4j OSGi: rama inalcanzable ejecutada\"); None }".into()},
                        ("java/util/stream/Stream","concat","(Ljava/util/stream/Stream;Ljava/util/stream/Stream;)Ljava/util/stream/Stream;") if self.multi_classes.is_some() && start==58 && self.active.last().is_some_and(|k| k=="org/apache/logging/log4j/util/ServiceLoaderUtil.safeStream(Ljava/lang/Class;Ljava/util/ServiceLoader;Lorg/apache/logging/log4j/Logger;)Ljava/util/stream/Stream;")=>{self.verify_log4j_absent_osgi()?;"{ error(\"Log4j OSGi: rama inalcanzable ejecutada\"); None }".into()},
                        ("java/util/concurrent/CompletableFuture","completedFuture","(Ljava/lang/Object;)Ljava/util/concurrent/CompletableFuture;") if self.multi_classes.is_some()=>{
                            if !futures_optin()? {return Err("completedFuture: requiere MC_AOT_FUTURES=restricted (alias histórico MC_AOT_FUTURES=completed-only o MC_AOT_NUMERIC_COMPLETED_FUTURE=1)".into());}
                            "Some(completed_future_new(heap,x0))".into()
                        },
                        ("java/util/concurrent/ConcurrentHashMap","newKeySet","()Ljava/util/concurrent/ConcurrentHashMap$KeySetView;") if self.multi_classes.is_some()=>"Some(concurrent_keyset_new(heap))".into(),
                        ("java/lang/Class","forName","(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;") if self.multi_classes.is_some()=>{
                            if std::env::var_os("MC_AOT_STANDARD_SYSTEM_LOADER").as_deref()!=Some(std::ffi::OsStr::new("1")){return Err("Class.forName(String,boolean,ClassLoader): requiere MC_AOT_STANDARD_SYSTEM_LOADER=1".into());}
                            "Some(class_for_name_three(heap,x0,x1,x2))".into()
                        },
                        ("java/lang/ClassLoader","getPlatformClassLoader","()Ljava/lang/ClassLoader;") if self.multi_classes.is_some()=>{
                            if std::env::var_os("MC_AOT_STANDARD_SYSTEM_LOADER").as_deref()!=Some(std::ffi::OsStr::new("1")){return Err("ClassLoader.getPlatformClassLoader: requiere MC_AOT_STANDARD_SYSTEM_LOADER=1".into());}
                            "Some(platform_class_loader(heap))".into()
                        },
                        ("java/lang/ClassLoader","getSystemClassLoader","()Ljava/lang/ClassLoader;") if self.multi_classes.is_some()=>{
                            if std::env::var_os("MC_AOT_STANDARD_SYSTEM_LOADER").as_deref()!=Some(std::ffi::OsStr::new("1")){return Err("ClassLoader.getSystemClassLoader: requiere MC_AOT_STANDARD_SYSTEM_LOADER=1".into());}
                            "Some(app_class_loader(heap))".into()
                        },
                        ("java/lang/Class","forName","(Ljava/lang/String;)Ljava/lang/Class;") if self.multi_classes.is_some()=>{
                            if std::env::var_os("MC_AOT_CLOSED_CLASSPATH").as_deref()!=Some(std::ffi::OsStr::new("1")){return Err("Class.forName: requiere MC_AOT_CLOSED_CLASSPATH=1".into());}
                            if super::classpath::has_class(self.jar,"org/osgi/framework/FrameworkUtil")? {return Err("Class.forName: FrameworkUtil presente fuera del perfil".into());}
                            "class_for_name_absent_osgi(heap,x0)".into()
                        },
                        ("java/util/Objects","toString","(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"objects_to_string_default(heap,x0,x1)".into(),
                        ("java/util/Comparator","comparingInt","(Ljava/util/function/ToIntFunction;)Ljava/util/Comparator;") if self.multi_classes.is_some()=>"Some(comparator_comparing_int(heap,x0))".into(),
                        ("java/util/Comparator","comparing","(Ljava/util/function/Function;)Ljava/util/Comparator;") if self.multi_classes.is_some()=>"Some(comparator_comparing(heap,x0))".into(),
                        ("java/util/Comparator","comparing","(Ljava/util/function/Function;Ljava/util/Comparator;)Ljava/util/Comparator;") if self.multi_classes.is_some()=>"Some(comparator_comparing_with(heap,x0,x1))".into(),
                        ("java/util/stream/StreamSupport","stream","(Ljava/util/Spliterator;Z)Ljava/util/stream/Stream;") if self.multi_classes.is_some()=>"Some(stream_support(heap,x0,x1))".into(),
                        ("java/util/Objects","requireNonNull","(Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"require_non_null(heap,x0,None)".into(),
                        ("java/util/Objects","requireNonNull","(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"require_non_null(heap,x0,x1)".into(),
                        ("java/util/UUID","randomUUID","()Ljava/util/UUID;") if self.multi_classes.is_some()=>"Some(uuid_random(heap))".into(),
                        ("java/util/regex/Pattern","compile","(Ljava/lang/String;I)Ljava/util/regex/Pattern;") if self.multi_classes.is_some()=>"Some(pattern_compile_duration(heap,x0,x1))".into(),
                        ("java/util/regex/Pattern","compile","(Ljava/lang/String;)Ljava/util/regex/Pattern;") if self.multi_classes.is_some()=>"Some(pattern_compile(heap,x0))".into(),
                        ("org/apache/logging/log4j/status/StatusLogger$PropertiesUtilsDouble","readAllAvailableProperties","()Ljava/util/Map;") if self.multi_classes.is_some()=>{self.verify_log4j_status_properties()?;"Some(status_properties_map(heap))".into()},
                        ("org/apache/logging/log4j/status/StatusLogger$PropertiesUtilsDouble","normalizePropertyName","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>{self.verify_log4j_status_properties()?;"Some(status_normalize_string(heap,x0))".into()},
                        ("java/lang/Enum","valueOf","(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/Enum;") if self.multi_classes.is_some()=>{self.uses_enum_valueof=true;"enum_valueof(heap,x0,x1)".into()},
                        ("java/util/EnumSet","allOf","(Ljava/lang/Class;)Ljava/util/EnumSet;") if self.multi_classes.is_some() && class=="org/apache/logging/log4j/spi/StandardLevel"=>{let (_,slot,_)=self.resolve_static_field(class,"$VALUES","[Lorg/apache/logging/log4j/spi/StandardLevel;")?;format!("Some(standardlevel_enumset(heap,x0,{slot}))")},
                        ("com/google/common/util/concurrent/MoreExecutors","newDirectExecutorService","()Lcom/google/common/util/concurrent/ListeningExecutorService;") if self.multi_classes.is_some()=>r#"{error("MoreExecutors.newDirectExecutorService: ejecución concurrente no implementada")}"#.into(),
                        ("java/util/stream/Collectors","toMap","(Ljava/util/function/Function;Ljava/util/function/Function;)Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_to_map(heap,x0,x1))".into(),
                        ("java/util/stream/Collectors","toUnmodifiableMap","(Ljava/util/function/Function;Ljava/util/function/Function;)Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_to_unmodifiable_map(heap,x0,x1))".into(),
                        ("java/lang/ScopedValue","newInstance","()Ljava/lang/ScopedValue;") if self.multi_classes.is_some()=>"Some(scoped_value_new(heap))".into(),
                        ("java/lang/ScopedValue","where","(Ljava/lang/ScopedValue;Ljava/lang/Object;)Ljava/lang/ScopedValue$Carrier;") if self.multi_classes.is_some()=>"Some(scoped_value_where(heap,x0,x1))".into(),
                        ("java/util/stream/Collectors","toMap","(Ljava/util/function/Function;Ljava/util/function/Function;Ljava/util/function/Function;)Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"{let c=pop_r(&mut stack);let b=pop_r(&mut stack);let a=pop_r(&mut stack);error(\"Collectors.toMap no soportado en este perfil\")}".into(),
                        ("java/util/stream/Collectors","toList","()Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_to_list(heap))".into(),
                        ("java/util/stream/Collectors","toSet","()Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_to_set(heap))".into(),
                        ("java/util/stream/Collectors","joining","(Ljava/lang/CharSequence;)Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_joining_delimiter(heap,x0))".into(),
                        ("java/util/stream/Collectors","joining","(Ljava/lang/CharSequence;Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_joining(heap,x0,x1,x2))".into(),
                        ("java/util/stream/Collector","of","(Ljava/util/function/Supplier;Ljava/util/function/BiConsumer;Ljava/util/function/BinaryOperator;[Ljava/util/stream/Collector$Characteristics;)Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collector_of(heap,x0,x1,x2,x3))".into(),
                        ("jdk/jfr/FlightRecorder","isAvailable","()Z") if self.multi_classes.is_some() && std::env::var("MC_AOT_DISABLE_JFR").as_deref()==Ok("1")=>"0".into(),
                        ("java/lang/System","identityHashCode","(Ljava/lang/Object;)I") if self.multi_classes.is_some()=>r#"{if x0.is_some(){error("System.identityHashCode: identidad de host no verificada");}0i32}"#.into(),
                        ("java/util/concurrent/Executors","defaultThreadFactory","()Ljava/util/concurrent/ThreadFactory;") if self.multi_classes.is_some()=>r#"{error("Executors.defaultThreadFactory: hilos no implementados")}"#.into(),
                        ("java/util/concurrent/Executors","newCachedThreadPool","(Ljava/util/concurrent/ThreadFactory;)Ljava/util/concurrent/ExecutorService;") if self.multi_classes.is_some()=>"Some(cached_thread_pool_new(heap,x0))".into(),
                        ("java/lang/System","currentTimeMillis","()J") if self.multi_classes.is_some()=>"current_time_millis()".into(),
                        ("java/lang/System","nanoTime","()J") if self.multi_classes.is_some()=>"nano_time()".into(),
                        ("java/lang/Thread","currentThread","()Ljava/lang/Thread;") if self.multi_classes.is_some()=>"Some(current_thread(heap))".into(),
                        ("java/lang/Thread","interrupted","()Z") if self.multi_classes.is_some()=>"thread_interrupted(heap) as i32".into(),
                        ("java/lang/Runtime","getRuntime","()Ljava/lang/Runtime;") if self.multi_classes.is_some()=>"Some(runtime_singleton(heap))".into(),
                        ("java/util/Arrays","sort","([C)V") if self.multi_classes.is_some()=>"array_sort_char(heap,x0)".into(),
                        ("java/util/Arrays","fill","([CC)V") if self.multi_classes.is_some()=>"array_fill_char(heap,x0,x1)".into(),
                        ("java/util/Arrays","fill","([BB)V") if self.multi_classes.is_some()=>"array_fill_byte(heap,x0,x1)".into(),
                        ("java/lang/Thread","holdsLock","(Ljava/lang/Object;)Z") if self.multi_classes.is_some()=>"monitor_holds(heap,x0) as i32".into(),
                        ("java/lang/System","arraycopy","(Ljava/lang/Object;ILjava/lang/Object;II)V") if self.multi_classes.is_some()=>"system_arraycopy(heap,x0,x1,x2,x3,x4)".into(),
                        ("net/minecraft/util/Util","startTimerHackThread","()V") if self.multi_classes.is_some()=>"util_start_timer_hack_thread_noop(heap)".into(),
                        ("java/lang/System","lineSeparator","()Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(system_line_separator(heap))".into(),
                        ("java/lang/System","setErr","(Ljava/io/PrintStream;)V") if self.multi_classes.is_some()=>"let s=pop_r(&mut stack);system_set_stream(heap,s);".into(),
                        ("java/lang/System","setOut","(Ljava/io/PrintStream;)V") if self.multi_classes.is_some()=>"let s=pop_r(&mut stack);system_set_stream(heap,s);".into(),
                        ("java/lang/ProcessHandle","current","()Ljava/lang/ProcessHandle;") if self.multi_classes.is_some()=>"Some(process_current(heap))".into(),
                        ("java/lang/Long","toString","(J)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(long_to_string(heap,x0))".into(),
                        ("java/net/URI","create","(Ljava/lang/String;)Ljava/net/URI;") if self.multi_classes.is_some()=>"Some(uri_create_common_link(heap,x0))".into(),
                        ("java/nio/file/Path","of","(Ljava/lang/String;[Ljava/lang/String;)Ljava/nio/file/Path;") | ("java/nio/file/Paths","get","(Ljava/lang/String;[Ljava/lang/String;)Ljava/nio/file/Path;") if self.multi_classes.is_some()=>"Some(path_of(heap,x0,x1))".into(),
                        ("java/nio/file/Files","newOutputStream","(Ljava/nio/file/Path;[Ljava/nio/file/OpenOption;)Ljava/io/OutputStream;") if self.multi_classes.is_some()=>"Some(files_new_output(heap,x0,x1))".into(),
                        ("java/nio/file/Files","newInputStream","(Ljava/nio/file/Path;[Ljava/nio/file/OpenOption;)Ljava/io/InputStream;") if self.multi_classes.is_some()=>"Some(files_new_input(heap,x0,x1))".into(),
                        ("java/nio/file/Files","exists"|"isDirectory"|"isRegularFile","(Ljava/nio/file/Path;[Ljava/nio/file/LinkOption;)Z") if self.multi_classes.is_some()=>format!("files_kind(heap,x0,x1,{method:?}) as i32"),
                        ("java/nio/file/Files","isSymbolicLink","(Ljava/nio/file/Path;)Z") if self.multi_classes.is_some()=>"files_symbolic_link(heap,x0) as i32".into(),
                        ("java/nio/file/Files","writeString","(Ljava/nio/file/Path;Ljava/lang/CharSequence;[Ljava/nio/file/OpenOption;)Ljava/nio/file/Path;") if self.multi_classes.is_some()=>"files_write_string(heap,x0,x1,x2)".into(),
                        ("java/time/ZoneId","systemDefault","()Ljava/time/ZoneId;") if self.multi_classes.is_some()=>r#"{error("ZoneId.systemDefault: zona predeterminada no implementada")}"#.into(),
                        ("java/time/ZoneId","of","(Ljava/lang/String;)Ljava/time/ZoneId;") if self.multi_classes.is_some()=>r#"{error("ZoneId.of: zona no implementada")}"#.into(),
                        ("java/time/format/DateTimeFormatter","ofPattern","(Ljava/lang/String;)Ljava/time/format/DateTimeFormatter;") if self.multi_classes.is_some()=>r#"{error("DateTimeFormatter.ofPattern: locale predeterminada no implementada")}"#.into(),
                        ("java/time/format/DateTimeFormatter","ofPattern","(Ljava/lang/String;Ljava/util/Locale;)Ljava/time/format/DateTimeFormatter;") if self.multi_classes.is_some()=>"Some(crash_date_formatter(heap,x0,x1))".into(),
                        ("java/time/ZonedDateTime","parse","(Ljava/lang/CharSequence;)Ljava/time/ZonedDateTime;") if self.multi_classes.is_some()=>"Some(zoned_parse(heap,x0))".into(),
                        ("java/util/Date","from","(Ljava/time/Instant;)Ljava/util/Date;") if self.multi_classes.is_some()=>"Some(date_from_instant(heap,x0))".into(),
                        ("java/lang/reflect/Array","getLength","(Ljava/lang/Object;)I") if self.multi_classes.is_some()=>"reflect_array_length(heap,x0)".into(),
                        ("java/util/List","of",_) if self.multi_classes.is_some() && (3..=10).contains(&call_sig.args.len()) && desc==format!("({})Ljava/util/List;","Ljava/lang/Object;".repeat(call_sig.args.len()))=>format!("Some(immutable_list_new(heap,vec![{}]))",(0..call_sig.args.len()).map(|i|format!("x{i}")).collect::<Vec<_>>().join(",")),
                        ("java/util/List","of","([Ljava/lang/Object;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(immutable_list_from_array(heap,x0))".into(),
                        ("java/util/List","of","()Ljava/util/List;") if self.multi_classes.is_some()=>"Some(immutable_list_new(heap,Vec::new()))".into(),
                        ("java/util/List","copyOf","(Ljava/util/Collection;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(list_copy_of(heap,x0))".into(),
                        ("java/util/List","of","(Ljava/lang/Object;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(immutable_list_new(heap,vec![x0]))".into(),
                        ("java/util/List","of","(Ljava/lang/Object;Ljava/lang/Object;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(immutable_list_new(heap,vec![x0,x1]))".into(),
                        ("java/util/Collections","newSetFromMap","(Ljava/util/Map;)Ljava/util/Set;") if self.multi_classes.is_some()=>"Some(identity_set_new(heap,x0))".into(),
                        ("java/util/Collections","sort","(Ljava/util/List;)V") if self.multi_classes.is_some()=>"{list_sort_strings(heap,x0);}".into(),
                        ("java/util/Arrays","sort","([Ljava/lang/Object;Ljava/util/Comparator;)V") if self.multi_classes.is_some()=>{self.interface_call("java/util/Comparator","compare","(Ljava/lang/Object;Ljava/lang/Object;)I")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/Comparator"&&v.1=="compare"&&v.2=="(Ljava/lang/Object;Ljava/lang/Object;)I").ok_or("Comparator.compare no registrada")?;format!("object_array_sort_comparator(heap,x0,x1,interface_dispatch_{id});").into()},
                        ("java/nio/file/spi/FileSystemProvider","installedProviders","()Ljava/util/List;") if self.multi_classes.is_some()=>"Some(installed_providers_zip(heap))".into(),
                        ("java/util/Collections","emptySet","()Ljava/util/Set;") if self.multi_classes.is_some()=>"Some(empty_set(heap))".into(),
                        ("java/util/Map","of",_) if self.multi_classes.is_some() && (2..=20).contains(&call_sig.args.len()) && call_sig.args.len()%2==0 && desc==format!("({})Ljava/util/Map;","Ljava/lang/Object;".repeat(call_sig.args.len()))=>format!("Some(map_of_n(heap,vec![{}]))",(0..call_sig.args.len()/2).map(|i|format!("(x{},x{})",i*2,i*2+1)).collect::<Vec<_>>().join(",")),
                        ("com/google/common/collect/ImmutableBiMap","of",_) if self.multi_classes.is_some() && (2..=20).contains(&call_sig.args.len()) && call_sig.args.len()%2==0 && desc==format!("({})Lcom/google/common/collect/ImmutableBiMap;","Ljava/lang/Object;".repeat(call_sig.args.len()))=>format!("Some(immutable_map_of_n(heap,vec![{}]))",(0..call_sig.args.len()/2).map(|i|format!("(x{},x{})",i*2,i*2+1)).collect::<Vec<_>>().join(",")),
                        ("com/google/common/collect/ImmutableMap","of",_) if self.multi_classes.is_some() && (2..=20).contains(&call_sig.args.len()) && call_sig.args.len()%2==0 && desc==format!("({})Lcom/google/common/collect/ImmutableMap;","Ljava/lang/Object;".repeat(call_sig.args.len()))=>format!("Some(immutable_map_of_n(heap,vec![{}]))",(0..call_sig.args.len()/2).map(|i|format!("(x{},x{})",i*2,i*2+1)).collect::<Vec<_>>().join(",")),
                        ("com/google/common/collect/ImmutableMap","of","()Lcom/google/common/collect/ImmutableMap;") if self.multi_classes.is_some()=>"Some(immutable_map_of_n(heap,vec![]))".into(),
                        ("com/google/common/hash/Hashing","md5","()Lcom/google/common/hash/HashFunction;") if self.multi_classes.is_some()=>"Some(hash_fn_md5(heap))".into(),
                        ("com/google/common/primitives/Longs","fromBytes","(BBBBBBBB)J") if self.multi_classes.is_some()=>"let b7=pop_i(&mut stack);let b6=pop_i(&mut stack);let b5=pop_i(&mut stack);let b4=pop_i(&mut stack);let b3=pop_i(&mut stack);let b2=pop_i(&mut stack);let b1=pop_i(&mut stack);let b0=pop_i(&mut stack);stack.push(V::L(i64::from_be_bytes([b0 as u8,b1 as u8,b2 as u8,b3 as u8,b4 as u8,b5 as u8,b6 as u8,b7 as u8])));".into(),
                        ("java/util/UUID","nameUUIDFromBytes","([B)Ljava/util/UUID;") if self.multi_classes.is_some()=>"Some(uuid_name_from_bytes(heap,x0))".into(),
                        ("java/util/UUID","fromString","(Ljava/lang/String;)Ljava/util/UUID;") if self.multi_classes.is_some()=>"Some(uuid_from_string(heap,x0))".into(),
                        ("java/lang/String","join","(Ljava/lang/CharSequence;Ljava/lang/Iterable;)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(string_join_iterable(heap,x0,x1))".into(),
                        ("net/minecraft/server/dedicated/DedicatedServerProperties","loadFromFile","(Ljava/nio/file/Path;)Ljava/util/Properties;") if self.multi_classes.is_some()=>"Some(settings_load_from_file(heap,x0))".into(),
                        ("net/minecraft/server/jsonrpc/security/SecurityConfig","generateSecretKey","()Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(security_config_generate_secret_key(heap))".into(),
                        ("java/util/OptionalLong","empty","()Ljava/util/OptionalLong;") if self.multi_classes.is_some()=>"Some(optional_long_empty(heap))".into(),
                        ("java/util/OptionalLong","of","(J)Ljava/util/OptionalLong;") if self.multi_classes.is_some()=>"Some(optional_long_of(heap,x0))".into(),
                        ("com/google/common/collect/ImmutableBiMap","of","()Lcom/google/common/collect/ImmutableBiMap;") if self.multi_classes.is_some()=>"Some(immutable_map_of_n(heap,vec![]))".into(),
                        ("java/util/Map","of","()Ljava/util/Map;") if self.multi_classes.is_some()=>"Some(empty_map(heap))".into(),
                        ("java/util/Set","of",_) if self.multi_classes.is_some() && (1..=10).contains(&call_sig.args.len()) && desc==format!("({})Ljava/util/Set;","Ljava/lang/Object;".repeat(call_sig.args.len()))=>format!("Some(set_of_n(heap,vec![{}]))",(0..call_sig.args.len()).map(|i|format!("x{i}")).collect::<Vec<_>>().join(",")),
                        ("java/util/Set","of","()Ljava/util/Set;") if self.multi_classes.is_some()=>"Some(empty_set(heap))".into(),
                        ("java/util/BitSet","valueOf","([J)Ljava/util/BitSet;") if self.multi_classes.is_some()=>"Some(bitset_of_longs(heap,x0))".into(),
                        ("java/util/BitSet","valueOf","([B)Ljava/util/BitSet;") if self.multi_classes.is_some()=>"Some(bitset_of_bytes(heap,x0))".into(),
                        ("java/util/stream/IntStream","range","(II)Ljava/util/stream/IntStream;") if self.multi_classes.is_some()=>"Some(int_stream_range(heap,x0,x1))".into(),
                        ("java/util/stream/IntStream","rangeClosed","(II)Ljava/util/stream/IntStream;") if self.multi_classes.is_some()=>"Some(int_stream_range(heap,x0,x1+1i32))".into(),
                        ("java/util/Set","of","([Ljava/lang/Object;)Ljava/util/Set;") if self.multi_classes.is_some()=>"Some(set_of_array(heap,x0))".into(),
                        ("java/util/Collections","emptyList","()Ljava/util/List;") if self.multi_classes.is_some()=>"Some(empty_list(heap))".into(),
                        ("java/util/Collections","emptyMap","()Ljava/util/Map;") if self.multi_classes.is_some()=>"Some(empty_map(heap))".into(),
                        ("java/util/Optional","empty","()Ljava/util/Optional;") if self.multi_classes.is_some()=>"Some(optional_new(heap,None))".into(),
                        ("java/util/Optional","ofNullable","(Ljava/lang/Object;)Ljava/util/Optional;") if self.multi_classes.is_some()=>"Some(optional_new(heap,x0))".into(),
                        ("java/util/Optional","of","(Ljava/lang/Object;)Ljava/util/Optional;") if self.multi_classes.is_some()=>"{if x0.is_none(){raise(\"NullPointerException\",\"\");}Some(optional_new(heap,x0))}".into(),
                        ("java/lang/Character","valueOf","(C)Ljava/lang/Character;") if self.multi_classes.is_some()=>"Some(box_character(heap,x0))".into(),
                        ("java/lang/Character","isWhitespace","(C)Z") if self.multi_classes.is_some()=>"character_whitespace_char(x0) as i32".into(),
                        ("java/lang/Character","toUpperCase","(C)C") if self.multi_classes.is_some()=>"character_upper_char(x0)".into(),
                        ("java/lang/Character","toString","(I)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(character_to_string(heap,x0))".into(),
                        ("java/util/function/Function","identity","()Ljava/util/function/Function;") if self.multi_classes.is_some()=>"Some(identity_function(heap))".into(),
                        ("java/lang/Long","numberOfLeadingZeros","(J)I") if self.multi_classes.is_some()=>"(x0 as u64).leading_zeros() as i32".into(),
                        ("java/lang/Integer","toHexString","(I)Ljava/lang/String;") if self.multi_classes.is_some()=>r#"Some(new_string(heap,format!("{:x}",x0 as u32).encode_utf16().collect()))"#.into(),
                        ("java/lang/reflect/Modifier", "isPublic"|"isPrivate"|"isProtected"|"isStatic"|"isFinal"|"isSynchronized"|"isVolatile"|"isTransient"|"isNative"|"isInterface"|"isAbstract"|"isStrict", "(I)Z") if self.multi_classes.is_some()=>{let bit=match method{"isPublic"=>1,"isPrivate"=>2,"isProtected"=>4,"isStatic"=>8,"isFinal"=>16,"isSynchronized"=>32,"isVolatile"=>64,"isTransient"=>128,"isNative"=>256,"isInterface"=>512,"isAbstract"=>1024,_=>2048};format!("((x0 & {bit}) != 0) as i32")},
                        ("java/lang/Integer","numberOfLeadingZeros","(I)I") if self.multi_classes.is_some()=>"(x0 as u32).leading_zeros() as i32".into(),
                        ("java/lang/Math","asin","(D)D") if self.multi_classes.is_some()=>"mth_asin(x0)".into(),
                        ("java/lang/Math","cos","(D)D") if self.multi_classes.is_some()=>"mth_cos(x0)".into(),
                        ("java/lang/Math","sqrt","(D)D") if self.multi_classes.is_some()=>"x0.sqrt()".into(),
                        ("java/lang/Math","ceil","(D)D") if self.multi_classes.is_some()=>"x0.ceil()".into(),
                        ("java/lang/Math","floor","(D)D") if self.multi_classes.is_some()=>"x0.floor()".into(),
                        ("java/lang/Math","rint","(D)D") if self.multi_classes.is_some()=>"x0.round_ties_even()".into(),
                        ("java/lang/Math","round","(D)J") if self.multi_classes.is_some()=>"(x0+0.5f64).floor() as i64".into(),
                        ("java/lang/Math","round","(F)I") if self.multi_classes.is_some()=>"(x0+0.5f32).floor() as i32".into(),
                        ("java/lang/Math","round","(F)J") if self.multi_classes.is_some()=>"(x0 as f64+0.5f64).floor() as i64".into(),
                        ("java/lang/Float","intBitsToFloat","(I)F") if self.multi_classes.is_some()=>"f32::from_bits(x0 as u32)".into(),
                        ("java/lang/Float","floatToRawIntBits","(F)I") if self.multi_classes.is_some()=>"x0.to_bits() as i32".into(),
                        ("java/lang/Float","floatToIntBits","(F)I") if self.multi_classes.is_some()=>"if x0.is_nan(){0x7fc00000u32 as i32}else{x0.to_bits() as i32}".into(),
                        ("java/lang/Float","isInfinite","(F)Z") if self.multi_classes.is_some()=>"i32::from(x0.is_infinite())".into(),
                        ("java/lang/Float","isNaN","(F)Z") if self.multi_classes.is_some()=>"i32::from(x0.is_nan())".into(),
                        ("java/lang/Double","isInfinite","(D)Z") if self.multi_classes.is_some()=>"i32::from(x0.is_infinite())".into(),
                        ("java/lang/Double","isNaN","(D)Z") if self.multi_classes.is_some()=>"i32::from(x0.is_nan())".into(),
                        ("java/lang/Double","longBitsToDouble","(J)D") if self.multi_classes.is_some()=>"f64::from_bits(x0 as u64)".into(),
                        ("java/lang/Double","doubleToRawLongBits","(D)J") if self.multi_classes.is_some()=>"x0.to_bits() as i64".into(),
                        ("java/lang/Double","doubleToLongBits","(D)J") if self.multi_classes.is_some()=>"if x0.is_nan(){0x7ff8000000000000u64 as i64}else{x0.to_bits() as i64}".into(),
                        ("java/lang/ThreadLocal","withInitial","(Ljava/util/function/Supplier;)Ljava/lang/ThreadLocal;") if self.multi_classes.is_some()=>"Some(threadlocal_with_initial(heap,x0))".into(),
                        ("java/text/DecimalFormatSymbols","getInstance","(Ljava/util/Locale;)Ljava/text/DecimalFormatSymbols;") if self.multi_classes.is_some()=>"Some(decimal_symbols_get_instance(heap,x0))".into(),
                        ("java/util/HexFormat","of","()Ljava/util/HexFormat;") if self.multi_classes.is_some()=>"Some(hex_format_of(heap))".into(),
                        // El envoltorio vivo no está modelado; gson lo origina sobre un
                        // ArrayList privado que nunca muta, así el snapshot es equivalente.
                        ("java/util/Collections","unmodifiableList","(Ljava/util/List;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(list_copy_of(heap,x0))".into(),
                        ("java/util/Collections","unmodifiableSet","(Ljava/util/Set;)Ljava/util/Set;") if self.multi_classes.is_some()=>"Some(set_copy_of(heap,x0))".into(),
                        ("java/util/Collections","singletonList","(Ljava/lang/Object;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(singleton_list(heap,x0))".into(),
                        ("java/util/Collections","singleton","(Ljava/lang/Object;)Ljava/util/Set;") if self.multi_classes.is_some()=>"Some(set_of_n(heap,vec![x0]))".into(),
                        ("java/util/concurrent/Executors","callable","(Ljava/lang/Runnable;Ljava/lang/Object;)Ljava/util/concurrent/Callable;") if self.multi_classes.is_some()=>"Some(callable_result_new(heap,x0,x1))".into(),
                        ("java/lang/System","getenv","()Ljava/util/Map;") if self.multi_classes.is_some()=>"Some(system_getenv_map(heap))".into(),
                        ("java/security/KeyStore","getInstance","(Ljava/lang/String;)Ljava/security/KeyStore;") if self.multi_classes.is_some()=>"{let _=x0;error(\"KeyStore.getInstance: no soportado (TLS auth chain; rama no modelada en el perfil AOT)\")}".into(),
                        ("java/security/KeyStore","getDefaultType","()Ljava/lang/String;") if self.multi_classes.is_some()=>"new_string(heap,[80,75,67,83,49,50].iter().copied().map(u16::from).collect())".into(),
                        ("javax/net/ssl/KeyManagerFactory","getDefaultAlgorithm","()Ljava/lang/String;") if self.multi_classes.is_some()=>"new_string(heap,[83,117,110,88,53,48,57].iter().copied().map(u16::from).collect())".into(),
                        ("javax/net/ssl/KeyManagerFactory","getInstance","(Ljava/lang/String;)Ljavax/net/ssl/KeyManagerFactory;") if self.multi_classes.is_some()=>"{let _=x0;error(\"KeyManagerFactory.getInstance: no soportado (TLS auth chain)\")}".into(),
                        ("javax/net/ssl/TrustManagerFactory","getDefaultAlgorithm","()Ljava/lang/String;") if self.multi_classes.is_some()=>"new_string(heap,[83,117,110,88,53,48,57].iter().copied().map(u16::from).collect())".into(),
                        ("javax/net/ssl/TrustManagerFactory","getInstance","(Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;") if self.multi_classes.is_some()=>"{let _=x0;error(\"TrustManagerFactory.getInstance: no soportado (TLS trust chain)\")}".into(),
                        ("java/security/cert/CertificateFactory","getInstance","(Ljava/lang/String;)Ljava/security/cert/CertificateFactory;") if self.multi_classes.is_some()=>"{let _=x0;error(\"CertificateFactory.getInstance: no soportado (TLS auth chain)\")}".into(),
                        ("java/lang/System","getenv","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"system_getenv(heap,x0)".into(),
                        ("java/nio/ByteBuffer","wrap","([B)Ljava/nio/ByteBuffer;") if self.multi_classes.is_some()=>"Some(byte_buffer_wrap(heap,x0))".into(),
                        ("java/util/HexFormat","fromHexDigits","(Ljava/lang/CharSequence;)I") if self.multi_classes.is_some()=>"let s=pop_r(&mut stack);stack.push(V::I(hex_from_digits(heap,s)));".into(),
                        ("java/time/Instant","now","()Ljava/time/Instant;") if self.multi_classes.is_some()=>"Some(instant_now(heap))".into(),
                        ("java/time/Duration","between","(Ljava/time/temporal/Temporal;Ljava/time/temporal/Temporal;)Ljava/time/Duration;") if self.multi_classes.is_some()=>"Some(duration_between_instants(heap,x0,x1))".into(),
                        ("java/time/Duration","ofMillis","(J)Ljava/time/Duration;") if self.multi_classes.is_some()=>"Some(duration_from_millis(heap,x0))".into(),
                        ("java/time/Duration","ofSeconds","(J)Ljava/time/Duration;") if self.multi_classes.is_some()=>"Some(duration_from_seconds(heap,x0))".into(),
                        ("java/time/Duration","ofMinutes","(J)Ljava/time/Duration;") if self.multi_classes.is_some()=>"Some(duration_from_minutes(heap,x0))".into(),
                        ("java/util/concurrent/Executors","newScheduledThreadPool","(ILjava/util/concurrent/ThreadFactory;)Ljava/util/concurrent/ScheduledExecutorService;") if self.multi_classes.is_some()=>"Some(scheduled_thread_pool_new(heap,x0,x1))".into(),
                        ("com/google/common/collect/Lists","newArrayList","()Ljava/util/ArrayList;") if self.multi_classes.is_some()=>"Some(lists_new_array_list(heap))".into(),
                        ("com/google/common/collect/Lists","reverse","(Ljava/util/List;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(lists_reverse(heap,x0))".into(),
                        ("com/google/common/io/Files","newReader","(Ljava/io/File;Ljava/nio/charset/Charset;)Ljava/io/BufferedReader;") if self.multi_classes.is_some()=>"Some(files_new_reader(heap,x0,x1))".into(),
                        ("java/nio/file/Files","newBufferedReader","(Ljava/nio/file/Path;)Ljava/io/BufferedReader;") if self.multi_classes.is_some()=>"Some(files_new_buffered_reader_path(heap,x0))".into(),
                        ("com/google/common/cache/CacheBuilder","newBuilder","()Lcom/google/common/cache/CacheBuilder;") if self.multi_classes.is_some()=>"Some(cache_builder_new(heap))".into(),
                        ("java/util/Objects","requireNonNullElse","(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;") if self.multi_classes.is_some()=>"if x0.is_some(){x0}else{x1}".into(),
                        ("java/lang/StackWalker","getInstance","()Ljava/lang/StackWalker;") if self.multi_classes.is_some()=>"Some(default_stack_walker(heap))".into(),
                        ("java/lang/StackWalker","getInstance","(Ljava/lang/StackWalker$Option;)Ljava/lang/StackWalker;") if self.multi_classes.is_some()=>"Some(stack_walker_new(heap,x0))".into(),
                        ("java/util/Arrays","fill","([Ljava/lang/Object;Ljava/lang/Object;)V") if self.multi_classes.is_some()=>"{ref_array_fill(heap,x0,x1);}".into(),
                        ("java/util/Arrays","copyOf","([II)[I") if self.multi_classes.is_some()=>"Some(int_array_copy_of(heap,x0,x1))".into(),
                        ("java/util/Arrays","copyOf","([Ljava/lang/Object;I)[Ljava/lang/Object;") if self.multi_classes.is_some()=>"Some(ref_array_copy_of(heap,x0,x1))".into(),
                        ("java/util/stream/Stream","of","([Ljava/lang/Object;)Ljava/util/stream/Stream;") if self.multi_classes.is_some()=>"Some(arrays_stream(heap,x0))".into(),
                        ("java/util/stream/Stream","of","(Ljava/lang/Object;)Ljava/util/stream/Stream;") if self.multi_classes.is_some()=>"Some(stream_of_single(heap,x0))".into(),
                        ("com/google/common/collect/ImmutableList","toImmutableList","()Ljava/util/stream/Collector;") if self.multi_classes.is_some()=>"Some(collectors_to_immutable_list(heap))".into(),
                        ("com/google/common/collect/ImmutableMap","copyOf","(Ljava/util/Map;)Lcom/google/common/collect/ImmutableMap;") if self.multi_classes.is_some()=>"Some(immutable_map_copy_of(heap,x0))".into(),
                        // El runtime no modela el contenedor inmutable concreto de JDK; los
                        // usos admiten un snapshot ImmutableMap equivalente (mismos nulls NPE).
                        ("java/util/Map","copyOf","(Ljava/util/Map;)Ljava/util/Map;") if self.multi_classes.is_some()=>"Some(immutable_map_copy_of(heap,x0))".into(),
                        ("java/util/Arrays","stream","([Ljava/lang/Object;)Ljava/util/stream/Stream;") if self.multi_classes.is_some()=>"Some(arrays_stream(heap,x0))".into(),
                        ("java/util/Arrays","asList","([Ljava/lang/Object;)Ljava/util/List;") if self.multi_classes.is_some()=>"Some(arrays_as_list(heap,x0))".into(),
                        ("java/lang/String","valueOf","(I)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(new_string(heap,x0.to_string().encode_utf16().collect()))".into(),
                        ("java/lang/String","valueOf","(J)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(new_string(heap,x0.to_string().encode_utf16().collect()))".into(),
                        ("java/lang/String","valueOf","(Z)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(string_literal(heap,if x0!=0{&[116,114,117,101]}else{&[102,97,108,115,101]}))".into(),
                        ("java/lang/String","valueOf","(C)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(new_string(heap,vec![x0 as u16]))".into(),
                        ("java/lang/String","valueOf","(Ljava/lang/Object;)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(string_value_of_object(heap,x0))".into(),
                        ("java/lang/Boolean","parseBoolean","(Ljava/lang/String;)Z") if self.multi_classes.is_some()=>"boolean_parse(heap,x0) as i32".into(),
                        ("java/lang/Short","valueOf","(S)Ljava/lang/Short;") if self.multi_classes.is_some()=>"Some(short_value_of(heap,x0))".into(),
                        ("java/lang/Double","valueOf","(D)Ljava/lang/Double;") if self.multi_classes.is_some()=>"Some(double_value_of(heap,x0))".into(),
                        ("java/lang/Float","valueOf","(F)Ljava/lang/Float;") if self.multi_classes.is_some()=>"Some(float_value_of(heap,x0))".into(),
                        ("java/lang/Long","valueOf","(J)Ljava/lang/Long;") if self.multi_classes.is_some()=>"Some(long_value_of(heap,x0))".into(),
                        ("java/lang/Integer","valueOf","(I)Ljava/lang/Integer;") if self.multi_classes.is_some()=>"Some(integer_value_of(heap,x0))".into(),
                        ("java/lang/Byte","valueOf","(B)Ljava/lang/Byte;") if self.multi_classes.is_some()=>"Some(byte_value_of(heap,x0))".into(),
                        ("java/lang/Integer","parseInt","(Ljava/lang/String;)I") if self.multi_classes.is_some()=>"integer_parse(heap,x0)".into(),
                        ("java/lang/Long","parseLong","(Ljava/lang/String;)J") if self.multi_classes.is_some()=>"long_parse(heap,x0)".into(),
                        ("java/lang/Boolean","valueOf","(Ljava/lang/String;)Ljava/lang/Boolean;") if self.multi_classes.is_some()=>"{let b=boolean_parse(heap,x0);Some(boolean_value_of(heap,b))}".into(),
                        ("java/lang/Boolean","valueOf","(Z)Ljava/lang/Boolean;") if self.multi_classes.is_some()=>"Some(boolean_value_of(heap,x0!=0))".into(),
                        ("java/util/ServiceLoader","load","(Ljava/lang/Class;Ljava/lang/ClassLoader;)Ljava/util/ServiceLoader;") if self.multi_classes.is_some()=>{self.uses_service_loader=true;"Some(service_load(heap,x0,x1,SERVICE_CATALOG))".into()},
                        ("java/lang/System","getSecurityManager","()Ljava/lang/SecurityManager;") if self.multi_classes.is_some()=>"None".into(),
                        ("java/lang/System","setSecurityManager","(Ljava/lang/SecurityManager;)V") if self.multi_classes.is_some()=>"raise(\"UnsupportedOperationException\",\"\")".into(),
                        ("java/lang/String","format","(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(string_format_basic(heap,x0,x1))".into(),
                        ("java/lang/String","format","(Ljava/util/Locale;Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;") if self.multi_classes.is_some()=>"Some(string_format_locale(heap,x0,x1,x2))".into(),
                        ("java/lang/System","getProperty","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"property_get(heap,x0)".into(),
                        ("java/lang/System","getProperty","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"property_get(heap,x0).or(x1)".into(),
                        ("java/lang/System","setProperty","(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"property_set(heap,x0,x1)".into(),
                        ("java/lang/System","clearProperty","(Ljava/lang/String;)Ljava/lang/String;") if self.multi_classes.is_some()=>"property_clear(heap,x0)".into(),
                        ("java/lang/Math","abs","(I)I")|("java/lang/Math","abs","(J)J") => "x0.wrapping_abs()".to_string(),
                        ("java/lang/Math","abs","(D)D")=>"x0.abs()".into(),
                        ("java/lang/Math","abs","(F)F")=>"x0.abs()".into(),
                        ("java/lang/Math","min","(II)I")|("java/lang/Math","min","(JJ)J")=>"std::cmp::min(x0,x1)".into(),
                        ("java/lang/Math","min","(DD)D")=>"java_min_d(x0,x1)".into(),
                        ("java/lang/Math","min","(FF)F")=>"java_min_f(x0,x1)".into(),
                        ("java/lang/Math","max","(DD)D")=>"java_max_d(x0,x1)".into(),
                        ("java/lang/Math","max","(FF)F")=>"java_max_f(x0,x1)".into(),
                        ("java/lang/Math","max","(II)I")|("java/lang/Math","max","(JJ)J")=>"std::cmp::max(x0,x1)".into(),
                        ("java/lang/Math","floorDiv","(II)I")=>"floor_div_i(x0,x1)".into(),
                        ("java/lang/Math","floorMod","(II)I")=>"floor_mod_i(x0,x1)".into(),
                        ("java/lang/Math","floorDiv","(JJ)J")=>"floor_div_l(x0,x1)".into(),
                        ("java/lang/Math","floorMod","(JJ)J")=>"floor_mod_l(x0,x1)".into(),
                        ("java/lang/Math","addExact","(II)I")=>"x0.checked_add(x1).unwrap_or_else(||raise(\"ArithmeticException\",\"integer overflow\"))".into(),
                        ("java/lang/Math","toIntExact","(J)I")=>"int_exact(x0)".into(),
                        ("java/util/Map","entry","(Ljava/lang/Object;Ljava/lang/Object;)Ljava/util/Map$Entry;") if self.multi_classes.is_some()=>"Some(map_entry_new(heap,x0,x1))".into(),
                        ("java/util/Map","ofEntries","([Ljava/util/Map$Entry;)Ljava/util/Map;") if self.multi_classes.is_some()=>"Some(of_entries(heap,x0))".into(),
                        ("java/util/logging/Logger","getLogger","(Ljava/lang/String;)Ljava/util/logging/Logger;") if self.multi_classes.is_some()=>"Some(logger_new(heap,x0))".into(),
                        ("java/nio/channels/spi/SelectorProvider","provider","()Ljava/nio/channels/spi/SelectorProvider;") if self.multi_classes.is_some()=>"Some(selector_provider_singleton(heap))".into(),
                        ("java/util/concurrent/atomic/AtomicReferenceFieldUpdater","newUpdater","(Ljava/lang/Class;Ljava/lang/Class;Ljava/lang/String;)Ljava/util/concurrent/atomic/AtomicReferenceFieldUpdater;") if self.multi_classes.is_some()=>"Some(aru_new(heap,x2))".into(),
                        ("java/util/Collections","addAll","(Ljava/util/Collection;[Ljava/lang/Object;)Z") if self.multi_classes.is_some()=>"(collections_add_all(heap,x0,x1) as i32)".into(),
                        ("java/lang/Character","isDigit","(C)Z") if self.multi_classes.is_some()=>"let c=pop_i(&mut stack);stack.push(V::I(char_is_digit(c) as i32));".into(),
                        ("java/lang/Character","isUpperCase","(C)Z") if self.multi_classes.is_some()=>"let c=pop_i(&mut stack);stack.push(V::I(character_is_upper_case(c) as i32));".into(),
                        ("java/lang/Character","isLowerCase","(C)Z") if self.multi_classes.is_some()=>"let c=pop_i(&mut stack);stack.push(V::I(character_is_lower_case(c) as i32));".into(),
                        ("java/lang/Character","toLowerCase","(C)C") if self.multi_classes.is_some()=>"let c=pop_i(&mut stack);stack.push(V::I(character_to_lower_char(c)));".into(),
                        ("java/util/Objects","requireNonNull","(Ljava/lang/Object;Ljava/util/function/Supplier;)Ljava/lang/Object;") if self.multi_classes.is_some()=>{ self.interface_call("java/util/function/Supplier","get","()Ljava/lang/Object;")?; let i=self.interface_calls.iter().position(|v|v.0=="java/util/function/Supplier"&&v.1=="get"&&v.2=="()Ljava/lang/Object;").ok_or("Supplier.get no registrada")?; format!("let supp=pop_r(&mut stack);let v=pop_r(&mut stack);if v.is_some(){{stack.push(V::R(v));}}else{{let _g=call_guard(\"<jdk-callback>\");let _=interface_dispatch_{i}(heap,supp);error(\"NullPointerException: requireNonNull(Object, Supplier)\")}}").into() },
                        ("java/lang/reflect/Array","newInstance","(Ljava/lang/Class;I)Ljava/lang/Object;") if self.multi_classes.is_some()=>"Some(reflect_array_new_instance(heap,x0,x1))".into(),
                        _ if callee==class||project_class(callee) => { let f=self.compile(callee,method,desc)?;format!("{f}(heap{})",if args.is_empty() {String::new()} else {format!(",{args}")}) },
                        _ => return Err(format!("invokestatic no soportado: {callee}.{method}{desc}")),
                    };
                    if call_sig.ret=='V' {format!("{pre}{expr};")}
                    else {format!("{pre}stack.push(V::{}({expr}));",variant(call_sig.ret))}
                },
                0xb9 => {
                    let idx=u16::from_be_bytes([read()?,read()?]);let count=read()? as usize;let zero=read()?;
                    let (owner,name,desc)=method_ref(&m.cp,idx)?;let sig=signature_ext(desc,self.multi_classes.is_some())?;
                    let expected=1+sig.args.iter().map(|t|if matches!(*t,'J'|'D'){2}else{1}).sum::<usize>();
                    if zero!=0 || count!=expected {return Err("invokeinterface inválido".into());}
                    if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","forEach","(Ljava/util/function/Consumer;)V") {
                        self.verify_log4j_service_spliterator()?;
                        self.interface_call("java/util/Spliterator","tryAdvance","(Ljava/util/function/Consumer;)Z")?;
                        self.interface_call("java/util/function/Consumer","accept","(Ljava/lang/Object;)V")?;
                        self.interface_call("java/util/function/Predicate","test","(Ljava/lang/Object;)Z")?;
                        let id=self.interface_calls.iter().position(|v|v.0=="java/util/Spliterator"&&v.1=="tryAdvance"&&v.2=="(Ljava/util/function/Consumer;)Z").ok_or("Spliterator.tryAdvance no registrado")?;
                        format!("let action=pop_r(&mut stack);let r=pop_r(&mut stack);stream_for_each(heap,r,action,interface_dispatch_{id});")
                    }
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Comparator","thenComparing","(Ljava/util/function/Function;)Ljava/util/Comparator;") {format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(comparator_then_comparing(heap,r,f))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Comparator","compare","(Ljava/lang/Object;Ljava/lang/Object;)I") {self.interface_call("java/util/function/Function","apply","(Ljava/lang/Object;)Ljava/lang/Object;")?;self.interface_call("java/util/function/ToIntFunction","applyAsInt","(Ljava/lang/Object;)I")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/Function"&&v.1=="apply"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("Function.apply no registrada")?;let tid=self.interface_calls.iter().position(|v|v.0=="java/util/function/ToIntFunction"&&v.1=="applyAsInt"&&v.2=="(Ljava/lang/Object;)I").ok_or("ToIntFunction.applyAsInt no registrada")?;format!("let b=pop_r(&mut stack);let a=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(comparator_compare(heap,r,a,b,interface_dispatch_{id},interface_dispatch_{tid}))); ")}
                    else if self.multi_classes.is_some() && matches!(owner,"java/util/Collection"|"java/util/List"|"java/util/Set") && name=="stream" && desc=="()Ljava/util/stream/Stream;" {"let r=pop_r(&mut stack);stack.push(V::R(Some(collection_stream(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","skip","(J)Ljava/util/stream/Stream;") {"let n=pop_l(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stack_stream_skip(heap,r,n))));".into()}
                    else if self.multi_classes.is_some() && (owner=="java/util/List"||owner=="java/util/Collection"||owner=="java/util/Set"||owner=="java/util/ArrayList") && name=="toArray" && desc=="(Ljava/util/function/IntFunction;)[Ljava/lang/Object;" {self.interface_call("java/util/function/IntFunction","apply","(I)Ljava/lang/Object;")?;let gen=self.interface_calls.iter().position(|v|v.0=="java/util/function/IntFunction"&&v.1=="apply"&&v.2=="(I)Ljava/lang/Object;").ok_or("IntFunction.apply no registrada")?;format!("let g=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(collection_to_array_gen(heap,r,g,interface_dispatch_{gen}))));")}
                    else if self.multi_classes.is_some() && (owner=="java/util/List"||owner=="java/util/Collection"||owner=="java/util/Set"||owner=="java/util/ArrayList") && name=="toArray" && desc=="()[Ljava/lang/Object;" {"let r=pop_r(&mut stack);stack.push(V::R(Some(collection_to_array(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","toArray","(Ljava/util/function/IntFunction;)[Ljava/lang/Object;") {self.interface_call("java/util/function/IntFunction","apply","(I)Ljava/lang/Object;")?;self.interface_call("java/util/function/Predicate","test","(Ljava/lang/Object;)Z")?;self.interface_call("java/util/function/ToIntFunction","applyAsInt","(Ljava/lang/Object;)I")?;let gen=self.interface_calls.iter().position(|v|v.0=="java/util/function/IntFunction"&&v.1=="apply"&&v.2=="(I)Ljava/lang/Object;").ok_or("IntFunction.apply no registrada")?;let test=self.interface_calls.iter().position(|v|v.0=="java/util/function/Predicate"&&v.1=="test"&&v.2=="(Ljava/lang/Object;)Z").ok_or("Predicate.test no registrada")?;let cmp=self.interface_calls.iter().position(|v|v.0=="java/util/function/ToIntFunction"&&v.1=="applyAsInt"&&v.2=="(Ljava/lang/Object;)I").ok_or("ToIntFunction.applyAsInt no registrada")?;format!("let g=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stream_to_array(heap,r,g,interface_dispatch_{cmp},interface_dispatch_{gen},interface_dispatch_{test}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","findFirst","()Ljava/util/Optional;") {self.interface_call("java/util/function/Function","apply","(Ljava/lang/Object;)Ljava/lang/Object;")?;self.interface_call("java/util/function/Predicate","test","(Ljava/lang/Object;)Z")?;let apply=self.interface_calls.iter().position(|v|v.0=="java/util/function/Function"&&v.1=="apply"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("Function.apply no registrada")?;let test=self.interface_calls.iter().position(|v|v.0=="java/util/function/Predicate"&&v.1=="test"&&v.2=="(Ljava/lang/Object;)Z").ok_or("Predicate.test no registrada")?;format!("let r=pop_r(&mut stack);stack.push(V::R(Some(stream_find_first(heap,r,interface_dispatch_{apply},interface_dispatch_{test}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/StackWalker$StackFrame","getClassName","()Ljava/lang/String;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(stack_frame_class_name(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/StackWalker$StackFrame","getDeclaringClass","()Ljava/lang/Class;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(stack_frame_class(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/IntStream","mapToObj","(Ljava/util/function/IntFunction;)Ljava/util/stream/Stream;") {self.interface_call("java/util/function/IntFunction","apply","(I)Ljava/lang/Object;")?;let i=self.interface_calls.iter().position(|v|v.0=="java/util/function/IntFunction"&&v.1=="apply"&&v.2=="(I)Ljava/lang/Object;").ok_or("IntFunction.apply no registrada")?;format!("let f=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(int_stream_map_to_obj(heap,r,f,interface_dispatch_{i}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("com/google/common/hash/HashFunction","hashString","(Ljava/lang/CharSequence;Ljava/nio/charset/Charset;)Lcom/google/common/hash/HashCode;") {"let cs=pop_r(&mut stack);let text=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(hash_fn_hash_string(heap,r,text,cs))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/IntStream","collect","(Ljava/util/function/Supplier;Ljava/util/function/ObjIntConsumer;Ljava/util/function/BiConsumer;)Ljava/lang/Object;") {self.interface_call("java/util/function/Supplier","get","()Ljava/lang/Object;")?;self.interface_call("java/util/function/ObjIntConsumer","accept","(Ljava/lang/Object;I)V")?;self.interface_call("java/util/function/BiConsumer","accept","(Ljava/lang/Object;Ljava/lang/Object;)V")?;let s=self.interface_calls.iter().position(|v|v.0=="java/util/function/Supplier"&&v.1=="get"&&v.2=="()Ljava/lang/Object;").ok_or("Supplier.get no registrada")?;let o=self.interface_calls.iter().position(|v|v.0=="java/util/function/ObjIntConsumer"&&v.1=="accept"&&v.2=="(Ljava/lang/Object;I)V").ok_or("ObjIntConsumer.accept no registrada")?;let b=self.interface_calls.iter().position(|v|v.0=="java/util/function/BiConsumer"&&v.1=="accept"&&v.2=="(Ljava/lang/Object;Ljava/lang/Object;)V").ok_or("BiConsumer.accept no registrada")?;format!("let c=pop_r(&mut stack);let f=pop_r(&mut stack);let sup=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(int_stream_collect(heap,r,sup,Some(f),Some(c),interface_dispatch_{s},interface_dispatch_{o},interface_dispatch_{b}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","collect","(Ljava/util/stream/Collector;)Ljava/lang/Object;") {self.interface_call("java/util/function/Predicate","test","(Ljava/lang/Object;)Z")?;self.interface_call("java/util/function/ToIntFunction","applyAsInt","(Ljava/lang/Object;)I")?;self.interface_call("java/util/function/Function","apply","(Ljava/lang/Object;)Ljava/lang/Object;")?;let test=self.interface_calls.iter().position(|v|v.0=="java/util/function/Predicate"&&v.1=="test"&&v.2=="(Ljava/lang/Object;)Z").ok_or("Predicate.test no registrada")?;let cmp=self.interface_calls.iter().position(|v|v.0=="java/util/function/ToIntFunction"&&v.1=="applyAsInt"&&v.2=="(Ljava/lang/Object;)I").ok_or("ToIntFunction.applyAsInt no registrada")?;let apply=self.interface_calls.iter().position(|v|v.0=="java/util/function/Function"&&v.1=="apply"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("Function.apply no registrada")?;format!("let c=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stream_collect(heap,r,c,interface_dispatch_{cmp},interface_dispatch_{test},interface_dispatch_{apply}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","toList","()Ljava/util/List;") {self.interface_call("java/util/function/Predicate","test","(Ljava/lang/Object;)Z")?;self.interface_call("java/util/function/ToIntFunction","applyAsInt","(Ljava/lang/Object;)I")?;let test=self.interface_calls.iter().position(|v|v.0=="java/util/function/Predicate"&&v.1=="test"&&v.2=="(Ljava/lang/Object;)Z").ok_or("Predicate.test no registrada")?;let cmp=self.interface_calls.iter().position(|v|v.0=="java/util/function/ToIntFunction"&&v.1=="applyAsInt"&&v.2=="(Ljava/lang/Object;)I").ok_or("ToIntFunction.applyAsInt no registrada")?;format!("let r=pop_r(&mut stack);stack.push(V::R(Some(stream_to_list(heap,r,interface_dispatch_{cmp},interface_dispatch_{test}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/concurrent/ScheduledExecutorService","execute","(Ljava/lang/Runnable;)V") {self.interface_call("java/lang/Runnable","run","()V")?;let id=self.interface_calls.iter().position(|v|v.0=="java/lang/Runnable"&&v.1=="run"&&v.2=="()V").ok_or("Runnable.run no registrada")?;format!("let task=pop_r(&mut stack);let r=pop_r(&mut stack);let _=scheduled_pool_id(heap,r);let _opaque=call_guard(\"<jdk-callback>\");interface_dispatch_{id}(heap,task);")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/concurrent/ScheduledExecutorService","schedule","(Ljava/lang/Runnable;JLjava/util/concurrent/TimeUnit;)Ljava/util/concurrent/ScheduledFuture;") {self.interface_call("java/lang/Runnable","run","()V")?;let id=self.interface_calls.iter().position(|v|v.0=="java/lang/Runnable"&&v.1=="run"&&v.2=="()V").ok_or("Runnable.run no registrada")?;format!("let unit=pop_i(&mut stack);let delay=pop_l(&mut stack);let task=pop_r(&mut stack);let r=pop_r(&mut stack);let nanos=delay.saturating_mul(timeunit_to_nanos(unit));let _=scheduled_pool_id(heap,r);stack.push(V::R(Some(scheduled_pool_schedule(heap,r,task,nanos,interface_dispatch_{id}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("com/google/common/cache/LoadingCache","getUnchecked","(Ljava/lang/Object;)Ljava/lang/Object;") {format!("let key=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(loading_cache_get(heap,r,key)));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("com/google/common/cache/LoadingCache","get","(Ljava/lang/Object;)Ljava/lang/Object;") {format!("let key=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(loading_cache_get(heap,r,key)));")}
                    else if self.multi_classes.is_some() && matches!(owner,"java/lang/Iterable"|"java/util/Collection"|"java/util/List"|"java/util/Set"|"java/util/SortedSet"|"java/util/NavigableSet"|"java/util/ArrayList"|"java/util/HashSet"|"java/util/LinkedHashSet"|"java/util/TreeSet"|"java/util/EnumSet"|"java/util/Queue"|"java/util/Deque"|"java/util/concurrent/ConcurrentLinkedQueue"|"java/util/concurrent/LinkedBlockingQueue") && name=="forEach" && desc=="(Ljava/util/function/Consumer;)V" {self.interface_call("java/util/function/Consumer","accept","(Ljava/lang/Object;)V")?;let i=self.interface_calls.iter().position(|v|v.0=="java/util/function/Consumer"&&v.1=="accept"&&v.2=="(Ljava/lang/Object;)V").ok_or("Consumer.accept no registrada")?;format!("let action=pop_r(&mut stack);let r=pop_r(&mut stack);collection_for_each(heap,r,action,interface_dispatch_{i});").into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Map","keySet","()Ljava/util/Set;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(map_key_set(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/ParameterizedType","getOwnerType","()Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);stack.push(V::R(gson_parameterized(heap,r,0)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/ParameterizedType","getRawType","()Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);stack.push(V::R(gson_parameterized(heap,r,1)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/ParameterizedType","getActualTypeArguments","()[Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);stack.push(V::R(gson_parameterized(heap,r,2)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/GenericArrayType","getGenericComponentType","()Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);stack.push(V::R(gson_generic_array(heap,r)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/WildcardType","getUpperBounds","()[Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);stack.push(V::R(gson_wildcard(heap,r,0)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/WildcardType","getLowerBounds","()[Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);stack.push(V::R(gson_wildcard(heap,r,1)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/function/Predicate","negate","()Ljava/util/function/Predicate;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(predicate_negate(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/TypeVariable","getBounds","()[Ljava/lang/reflect/Type;") {"let r=pop_r(&mut stack);let _=array_id(heap,r);error(\"TypeVariable.getBounds: reflexión de genéricos no modelada (trama de gson compilable; no alcanzada en el boot)\");stack.push(V::R(None));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Map","forEach","(Ljava/util/function/BiConsumer;)V") {self.interface_call("java/util/function/BiConsumer","accept","(Ljava/lang/Object;Ljava/lang/Object;)V")?;let i=self.interface_calls.iter().position(|v|v.0=="java/util/function/BiConsumer"&&v.1=="accept"&&v.2=="(Ljava/lang/Object;Ljava/lang/Object;)V").ok_or("BiConsumer.accept no registrada")?;format!("let action=pop_r(&mut stack);let r=pop_r(&mut stack);map_for_each(heap,r,action,interface_dispatch_{i});").into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/List","hashCode","()I") {let id=self.register_object_hashcode();format!("let r=pop_r(&mut stack);stack.push(V::I(list_hash(heap,r,virtual_dispatch_{id})));").into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","dropWhile","(Ljava/util/function/Predicate;)Ljava/util/stream/Stream;") {"let pred=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stack_stage_new(heap,r,pred,1))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","flatMap","(Ljava/util/function/Function;)Ljava/util/stream/Stream;") {"let f=pop_r(&mut stack);let r=pop_r(&mut stack);let _=(f,r);error(\"Stream.flatMap: no soportado (el perfil AOT no recorre Dynamic<Dynamic>)\");".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/nio/file/Path","toRealPath","([Ljava/nio/file/LinkOption;)Ljava/nio/file/Path;") {"let options=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(path_real_path(heap,r,options)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","map","(Ljava/util/function/Function;)Ljava/util/stream/Stream;") {"let f=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stream_map(heap,r,f))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","max","(Ljava/util/Comparator;)Ljava/util/Optional;") {self.interface_call("java/util/function/Function","apply","(Ljava/lang/Object;)Ljava/lang/Object;")?;self.interface_call("java/util/function/ToIntFunction","applyAsInt","(Ljava/lang/Object;)I")?;let id=self.interface_calls.iter().position(|v|v.0=="java/util/function/Function"&&v.1=="apply"&&v.2=="(Ljava/lang/Object;)Ljava/lang/Object;").ok_or("Function.apply no registrada")?;let tid=self.interface_calls.iter().position(|v|v.0=="java/util/function/ToIntFunction"&&v.1=="applyAsInt"&&v.2=="(Ljava/lang/Object;)I").ok_or("ToIntFunction.applyAsInt no registrada")?;format!("let cmp=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stream_max_list(heap,r,cmp,interface_dispatch_{id},interface_dispatch_{tid}))));")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","sorted","(Ljava/util/Comparator;)Ljava/util/stream/Stream;") {"let cmp=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stream_sorted(heap,r,cmp))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/stream/Stream","filter","(Ljava/util/function/Predicate;)Ljava/util/stream/Stream;") {"let pred=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(stream_filter(heap,r,pred))));".into()}
                    else if self.multi_classes.is_some() && matches!(owner,"java/util/stream/Stream"|"java/util/stream/BaseStream") && name=="isParallel" && desc=="()Z" {"let r=pop_r(&mut stack);stack.push(V::I(stream_is_parallel(heap,r) as i32));".into()}
                    else if self.multi_classes.is_some() && matches!(owner,"java/util/stream/Stream"|"java/util/stream/BaseStream") && name=="close" && desc=="()V" {"let r=pop_r(&mut stack);stream_close(heap,r);".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Spliterator","estimateSize","()J") {"let r=pop_r(&mut stack);stack.push(V::L(spliterator_state(heap,r).0));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Spliterator","characteristics","()I") {"let r=pop_r(&mut stack);stack.push(V::I(spliterator_state(heap,r).1));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Spliterator","getExactSizeIfKnown","()J") {"let r=pop_r(&mut stack);let (size,flags)=spliterator_state(heap,r);stack.push(V::L(if flags&64!=0 {size} else {-1}));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Spliterator","hasCharacteristics","(I)Z") {"let wanted=pop_i(&mut stack);let r=pop_r(&mut stack);let flags=spliterator_state(heap,r).1;stack.push(V::I(((flags&wanted)==wanted) as i32));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/nio/file/Path","resolve","(Ljava/lang/String;)Ljava/nio/file/Path;") {"let s=pop_r(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(path_resolve(heap,r,s))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/nio/file/Path","toAbsolutePath","()Ljava/nio/file/Path;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(path_absolute(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/nio/file/Path","getParent","()Ljava/nio/file/Path;") {"let r=pop_r(&mut stack);stack.push(V::R(path_parent(heap,r)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/nio/file/Path","toString","()Ljava/lang/String;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(path_to_string(heap,r))));".into()}
                    else if self.multi_classes.is_some() && owner=="java/util/concurrent/locks/ReadWriteLock" && matches!(name,"readLock"|"writeLock") && desc=="()Ljava/util/concurrent/locks/Lock;" {format!("let r=pop_r(&mut stack);let id=rw_lock_view(heap,r,{});stack.push(V::R(Some(id)));",name=="readLock")}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/concurrent/locks/Lock","lock","()V") {"let r=pop_r(&mut stack);reentrant_lock(heap,r);".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/concurrent/locks/Lock","lockInterruptibly","()V") {"let r=pop_r(&mut stack);let _=array_id(heap,r);if thread_interrupted(heap){raise(\"InterruptedException\",\"\");}reentrant_lock(heap,r);".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/concurrent/locks/Lock","unlock","()V") {"let r=pop_r(&mut stack);reentrant_unlock(heap,r);".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/ProcessHandle","pid","()J") {"let r=pop_r(&mut stack);stack.push(V::L(process_pid(heap,r)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/Member","getModifiers","()I") {"let r=pop_r(&mut stack);stack.push(V::I(member_modifiers(heap,r,REFLECT_CTOR_MODIFIERS,REFLECT_METHOD_MODIFIERS)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/reflect/Member","getDeclaringClass","()Ljava/lang/Class;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(member_declaring_class(heap,r,REFLECT_METHODS))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Map$Entry","getKey","()Ljava/lang/Object;") {"let r=pop_r(&mut stack);stack.push(V::R(map_entry_key(heap,r)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Map$Entry","getValue","()Ljava/lang/Object;") {"let r=pop_r(&mut stack);stack.push(V::R(map_entry_value(heap,r)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/CharSequence","toString","()Ljava/lang/String;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(char_sequence_to_string(heap,r))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/CharSequence","subSequence","(II)Ljava/lang/CharSequence;") {"let end=pop_i(&mut stack);let begin=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::R(Some(char_sequence_subsequence(heap,r,begin,end))));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/CharSequence","length","()I") {"let r=pop_r(&mut stack);stack.push(V::I(char_sequence_length(heap,r)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/CharSequence","charAt","(I)C") {"let i=pop_i(&mut stack);let r=pop_r(&mut stack);stack.push(V::I(char_sequence_at(heap,r,i)));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Enumeration","hasMoreElements","()Z") {"let r=pop_r(&mut stack);stack.push(V::I(empty_enumeration_has_next(heap,r) as i32));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Enumeration","nextElement","()Ljava/lang/Object;") {"let r=pop_r(&mut stack);empty_enumeration_next(heap,r);".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/lang/Iterable","iterator","()Ljava/util/Iterator;") {"let r=pop_r(&mut stack);stack.push(V::R(Some(iterable_iterator(heap,r))));".into()}
                    else                     if self.multi_classes.is_some() && project_class(owner) && name=="getClass" && desc=="()Ljava/lang/Class;" {self.verify_cast_interface(owner)?;format!("let r=pop_r(&mut stack);if r.is_some()&&!project_instance(heap,r,{owner:?},PROJECT_INTERFACES){{error(\"invokeinterface getClass: receptor incompatible\");}}stack.push(V::R(Some(object_get_class(heap,r))));")}
                    else                     if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Iterator","hasNext","()Z") {"let r=pop_r(&mut stack);stack.push(V::I(iterator_has_next(heap,r,REFLECT_CTORS,PROJECT_INTERFACES) as i32));".into()}
                    else if self.multi_classes.is_some() && (owner,name,desc)==("java/util/Iterator","next","()Ljava/lang/Object;") {"let r=pop_r(&mut stack);stack.push(V::R(iterator_next(heap,r,REFLECT_CTORS,PROJECT_INTERFACES,reflect_construct)));".into()}
                    else if self.multi_classes.is_some() && matches!(owner,"java/util/concurrent/ConcurrentMap"|"java/util/Map") && name=="computeIfAbsent" && desc=="(Ljava/lang/Object;Ljava/util/function/Function;)Ljava/lang/Object;" {self.map_compute_if_absent()?}
                    else if self.multi_classes.is_some() && collection_intrinsic(owner,name,desc).is_some() {collection_intrinsic(owner,name,desc).unwrap().into()}
                    else if self.multi_classes.is_some() && (project_class(owner)||jdk_function_interface(owner)) {self.interface_call(owner,name,desc)?}
                    else {return Err(format!("invokeinterface no soportado: {owner}.{name}{desc}"));}
                },
                0xba => {
                    let idx=u16::from_be_bytes([read()?,read()?]);if read()?!=0||read()?!=0{return Err("invokedynamic bytes reservados inválidos".into());}
                    if self.multi_classes.is_none(){return Err("invokedynamic concat solo en multi-static-demo".into());}
                    self.invoke_dynamic(m,class,idx)?
                },
                0xbb => {
                    let idx=u16::from_be_bytes([read()?,read()?]);
                    let class=match m.cp.get(idx as usize) {Some(CpEntry::Class(u))=>super::utf(&m.cp,*u)?,_=>return Err("new Class inválida".into())};
                    if known_exception(class).is_some() || (project_class(class) && self.resolve_exception_type(class).is_ok()) {
                        self.validate_exception_class(class)?;let kind=known_exception(class).unwrap_or(class);
                        format!("stack.push(V::R(Some(new_exception(heap,{kind:?}))));")
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/CopyOnWriteArrayList" {r#"error("CopyOnWriteArrayList: concurrencia no implementada");"#.into()
                    } else if self.multi_classes.is_some() && class=="java/util/Properties" {"stack.push(V::R(Some(java_properties_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/io/File" {"stack.push(V::R(Some(file_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/locks/ReentrantReadWriteLock" {"stack.push(V::R(Some(rw_lock_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/locks/ReentrantLock" {"stack.push(V::R(Some(reentrant_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/atomic/AtomicInteger" {"stack.push(V::R(Some(atomic_integer_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/atomic/AtomicLong" {"stack.push(V::R(Some(atomic_long_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/atomic/AtomicBoolean" {"stack.push(V::R(Some(atomic_boolean_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/atomic/AtomicReference" {
                        "stack.push(V::R(Some(atomic_ref_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/LinkedHashMap" {"stack.push(V::R(Some(linked_map_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/TreeMap" {"stack.push(V::R(Some(tree_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/lang/String" {"stack.push(V::R(Some(new_string(heap,Vec::new()))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/IdentityHashMap" {"stack.push(V::R(Some(identity_map_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/HashMap" {"stack.push(V::R(Some(hashmap_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/io/ByteArrayInputStream" {"stack.push(V::R(Some(byte_input_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/io/FileInputStream" {"stack.push(V::R(Some(file_input_pending_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/io/InputStreamReader" {"stack.push(V::R(Some(reader_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/zip/GZIPOutputStream" {"stack.push(V::R(Some(gzip_out_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/zip/GZIPInputStream" {"stack.push(V::R(Some(gzip_in_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/zip/DeflaterOutputStream" {"stack.push(V::R(Some(deflate_out_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/zip/InflaterInputStream" {"stack.push(V::R(Some(deflate_in_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/io/BufferedOutputStream" {"stack.push(V::R(Some(buffered_output_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/net/URL" {"stack.push(V::R(Some(url_pending_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/CompletableFuture" {
                        if !futures_optin()? {return Err("CompletableFuture: requiere MC_AOT_FUTURES=restricted (alias histórico MC_AOT_FUTURES=completed-only o MC_AOT_NUMERIC_COMPLETED_FUTURE=1)".into());}
                        "stack.push(V::R(Some(pending_future_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="com/google/gson/GsonBuilder" {"stack.push(V::R(Some(gson_builder_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="com/google/common/cache/CacheBuilder" {"stack.push(V::R(Some(cache_builder_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/io/StringReader" {"stack.push(V::R(Some(reader_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/WeakHashMap" {"error(\"new WeakHashMap: semántica de claves débiles no implementada\");".into()
                    } else if self.multi_classes.is_some() && class=="java/text/DecimalFormat" {"stack.push(V::R(Some(decimal_format_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/text/SimpleDateFormat" {"error(\"new SimpleDateFormat: no soportado\");".into()
                    } else if self.multi_classes.is_some() && class=="java/io/FileOutputStream" {"error(\"new FileOutputStream: no soportado\");".into()
                    } else if self.multi_classes.is_some() && class=="java/io/PrintStream" {"error(\"new PrintStream: no soportado\");".into()
                    } else if self.multi_classes.is_some() && class=="java/lang/ref/WeakReference" {"stack.push(V::R(Some(weak_loader_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/concurrent/ForkJoinPool" {"stack.push(V::R(Some(forkjoin_pool_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/UUID" {"stack.push(V::R(Some(uuid_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/BitSet" {"stack.push(V::R(Some(bitset_new(heap,0))));".into()
                    } else if self.multi_classes.is_some() && class=="java/lang/RuntimePermission" {"stack.push(V::R(Some(runtime_permission_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/Date" {
                        "stack.push(V::R(Some(date_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/lang/StringBuilder" {
                        "stack.push(V::R(Some(builder_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/lang/ThreadLocal" {
                        "stack.push(V::R(Some(threadlocal_new(heap))));".into()
                    } else if self.multi_classes.is_some() && matches!(class,"java/util/concurrent/ConcurrentHashMap"|"java/util/concurrent/LinkedBlockingQueue"|"java/util/concurrent/ConcurrentLinkedQueue"|"java/util/ArrayDeque"|"java/util/ArrayList"|"java/util/HashSet"|"java/util/LinkedHashSet"|"java/util/TreeSet") {
                        format!("stack.push(V::R(Some(collection_new(heap,{class:?}))));")
                    } else if self.multi_classes.is_some() && class=="java/lang/Object" {
                        "stack.push(V::R(Some(object_new(heap,\"java/lang/Object\",vec![],false))));".into()
                    } else if self.multi_classes.is_some() && class=="java/lang/StackTraceElement" {"stack.push(V::R(Some(stack_element_new(heap))));".into()
                    } else if self.multi_classes.is_some() && class=="java/util/EnumMap" {"stack.push(V::R(Some(enum_map_new(heap))));".into()
                    } else if self.multi_classes.is_some() && project_class(class) {
                        let id=self.ensure_multi_class(class)?;
                        if self.multi_classes.as_ref().unwrap()[id].flags&0x0400!=0 {return Err(format!("new de clase abstracta no soportado: {class}"));}
                        let fields=self.instance_layout(class)?;
                        let defaults=fields.iter().map(|f|f.initial.as_str()).collect::<Vec<_>>().join(",");
                        let inheritable=self.multi_classes.as_ref().unwrap()[id].inheritable_local;
                        format!("init_class_{id}(heap);stack.push(V::R(Some(object_new(heap,{class:?},vec![{defaults}],{inheritable}))));")
                    } else {return Err(format!("new no soportado: {class}"));}
                },
                0xbc => {
                    let kind=read()?;
                    if !matches!(kind,4|5|8|9|10|11) && !(self.multi_classes.is_some()&&matches!(kind,6|7)) {return Err(format!("newarray tipo no soportado {kind} en {start}"));}
                    format!("let n=pop_i(&mut stack); stack.push(V::R(Some(array_new(heap,{kind},n))));")
                },
                0xbd => {
                    let idx=u16::from_be_bytes([read()?,read()?]);
                    let name=match m.cp.get(idx as usize) {Some(CpEntry::Class(u))=>super::utf(&m.cp,*u)?,_=>return Err("anewarray Class inválida".into())};
                    if self.multi_classes.is_some() && name=="[I" {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(ref_array_new(heap,n))));")
                    } else if self.multi_classes.is_some() && name=="java/lang/reflect/Type" {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(array_new(heap,15,n))));")
                    } else if self.multi_classes.is_some() && project_class(name) {
                        self.verify_project_cast_target(name)?;let data=class_from_jar(self.jar,name)?;let meta=super::metadata::parse(&data)?;
                        if name!="org/apache/logging/log4j/Marker" && meta.flags&0x0010==0 && !(meta.flags&0x4000!=0&&meta.parent.as_deref()==Some("java/lang/Enum")) {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(project_empty_array_new(heap,{name:?},n))));")}
                        else {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(project_array_new(heap,{name:?},n))));")}
                    } else if self.multi_classes.is_some() && matches!(name,"java/lang/Integer"|"java/lang/Boolean"|"java/lang/Character"|"java/lang/Long"|"java/lang/Byte"|"java/lang/Float") {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(project_array_new(heap,{name:?},n))));")
                    } else if self.multi_classes.is_some() && name=="java/lang/ClassLoader" {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(project_array_new(heap,{name:?},n))));")
                    } else if self.multi_classes.is_some() && name=="java/lang/CharSequence" {format!("let n=pop_i(&mut stack);stack.push(V::R(Some(project_array_new(heap,{name:?},n))));")
                    } else if self.multi_classes.is_some() && matches!(name,"java/util/stream/Collector$Characteristics"|"java/nio/file/OpenOption"|"java/nio/file/LinkOption"|"java/lang/Boolean"|"java/lang/Byte"|"java/lang/Character"|"java/lang/Double"|"java/lang/Float"|"java/lang/Integer"|"java/lang/Long"|"java/lang/Short"|"java/lang/reflect/Field"|"java/lang/reflect/Method"|"java/lang/reflect/Type"|"java/lang/StackTraceElement"|"java/nio/ByteBuffer"|"java/security/cert/Certificate"|"java/security/cert/X509Certificate"|"javax/security/cert/X509Certificate"|"java/util/Map$Entry"|"java/lang/Throwable") {
                        format!("let n=pop_i(&mut stack);stack.push(V::R(Some(jdk_empty_array_new(heap,{name:?},n))));")
                    }else {
                        let kind=match name {"java/lang/String"=>12,"java/lang/Object" if self.multi_classes.is_some()=>13,"java/lang/Class" if self.multi_classes.is_some()=>14,_=>return Err(format!("anewarray no soportado: {name}"))};
                        format!("let n=pop_i(&mut stack); stack.push(V::R(Some(array_new(heap,{kind},n))));")
                    }
                },
                0xc5 => {
                    let idx=u16::from_be_bytes([read()?,read()?]);let count=read()?;
                    let name=match m.cp.get(idx as usize) {Some(CpEntry::Class(u))=>super::utf(&m.cp,*u)?,_=>return Err("multianewarray Class inválida".into())};
                    if count==2 && name.starts_with("[[L") && name.ends_with(';') {
                        let component=&name[3..name.len()-1];
                        if project_class(component) {
                            self.verify_project_cast_target(component)?;let component=component.to_owned();
                            format!("let d2=pop_i(&mut stack);let d1=pop_i(&mut stack);stack.push(V::R(Some(multi_project_ref_array_new_2d(heap,{component:?},d1,d2))));")
                        } else {return Err(format!("multianewarray componente no proyecto: {name}"))}
                    } else {return Err(format!("multianewarray no soportado: {count}x {name}"))}
                },
                0xbe => "let a=pop_r(&mut stack); stack.push(V::I(array_len(heap,a)));".into(),
                0xbf => {fall=false; "let r=pop_r(&mut stack); throw_ref(heap,r);".into()},
                0xc2|0xc3 => {
                    if self.multi_classes.is_none(){return Err("monitores solo en multi-static monohilo".into());}
                    if op==0xc2 {"let r=pop_r(&mut stack);monitor_enter(heap,r);".into()} else {"let r=pop_r(&mut stack);monitor_exit(heap,r);".into()}
                },
                0xc0|0xc1 => {
                    let idx=u16::from_be_bytes([read()?,read()?]);
                    let name=match m.cp.get(idx as usize) {Some(CpEntry::Class(u))=>super::utf(&m.cp,*u)?,_=>return Err("tipo de cast inválido".into())};
                    let pred=if self.multi_classes.is_some() && name.starts_with("[[L") && name.ends_with(';') && project_class(&name[3..name.len()-1]) {
                        let component=&name[3..name.len()-1];let component=component.to_owned();self.verify_project_cast_target(&component)?;
                        format!("project_2d_ref_array_instance(heap,r,{component:?})")
                    } else if self.multi_classes.is_some() && project_array(name).is_some() {
                        let component=project_array(name).unwrap();self.verify_project_cast_target(component)?;let data=class_from_jar(self.jar,component)?;let meta=super::metadata::parse(&data)?;
                        if meta.flags&0x0010==0 {format!("project_nonfinal_array_instance(heap,r,{component:?})")}else{format!("project_array_instance(heap,r,{component:?})")}
                    } else if self.multi_classes.is_some() && matches!(name,"[F"|"[D"|"[I"|"[J"|"[Z"|"[B"|"[C"|"[S") {format!("primitive_array_instance(heap,r,{name:?})")
                    } else if self.multi_classes.is_some() && matches!(name,"[Ljava/nio/file/LinkOption;"|"[Ljava/nio/file/OpenOption;") {let component=&name[2..name.len()-1];format!("project_array_instance(heap,r,{component:?})")
                    } else if self.multi_classes.is_some() && name=="[Ljava/lang/CharSequence;" {
                        "charsequence_array_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/util/Collection" {"collection_instance(heap,r,PROJECT_INTERFACES)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/lang/reflect/Member" {"member_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/util/Date" {"date_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/time/temporal/Temporal" {"temporal_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/lang/StackTraceElement" {"false".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/lang/CharSequence" {"charsequence_instance(heap,r,PROJECT_INTERFACES)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/nio/file/Path" {"path_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/util/RandomAccess" {"list_random_access_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/util/Map$Entry" {"tree_entry_instance(heap,r)".to_owned()
                    } else if self.multi_classes.is_some() && name=="java/io/Serializable" {
                        "serializable_instance(heap,r,PROJECT_INTERFACES)".to_owned()
                    } else if self.multi_classes.is_some() && (known_exception(name).is_some() || (project_class(name) && self.resolve_exception_type(name).is_ok())) {
                        format!("exception_instance(heap,r,{name:?})")
                    } else if self.multi_classes.is_some() && jdk_function_interface(name) {
                        format!("project_instance(heap,r,{name:?},PROJECT_INTERFACES)")
                    } else if self.multi_classes.is_some() && project_class(name) && !name.starts_with('[') {
                        self.verify_project_cast_target(name)?;
                        format!("project_instance(heap,r,{name:?},PROJECT_INTERFACES)")
                    } else {
                        let kind=match name {"java/lang/String"=>"s","java/io/PrintStream" if self.multi_classes.is_some()=>"printstream","java/lang/ClassLoader" if self.multi_classes.is_some()=>"classloader","java/lang/Class" if self.multi_classes.is_some()=>"class","java/util/Optional" if self.multi_classes.is_some()=>"optional","java/util/concurrent/CompletableFuture" if self.multi_classes.is_some() && futures_optin().ok()==Some(true)=>"completedfuture","java/net/URI" if self.multi_classes.is_some()=>"uri","java/nio/file/spi/FileSystemProvider" if self.multi_classes.is_some()=>"zipfsprovider","java/util/BitSet" if self.multi_classes.is_some()=>"bitset","java/lang/Enum" if self.multi_classes.is_some()=>"enum","java/lang/StackWalker$StackFrame" if self.multi_classes.is_some()=>"stackframe","java/util/stream/Stream" if self.multi_classes.is_some()=>"stream","java/util/Map" if self.multi_classes.is_some()=>"map","java/util/concurrent/ConcurrentMap" if self.multi_classes.is_some()=>"concurrentmap","java/util/List" if self.multi_classes.is_some()=>"list","java/util/Set" if self.multi_classes.is_some()=>"set","java/lang/Number" if self.multi_classes.is_some()=>"number","java/lang/StringBuilder" if self.multi_classes.is_some()=>"builder","java/io/Reader" if self.multi_classes.is_some()=>"reader","java/io/InputStream" if self.multi_classes.is_some()=>"inputstream","java/lang/Integer" if self.multi_classes.is_some()=>"integer","java/lang/Boolean" if self.multi_classes.is_some()=>"boolean","java/lang/Long" if self.multi_classes.is_some()=>"long","java/lang/Short" if self.multi_classes.is_some()=>"short","java/lang/Character" if self.multi_classes.is_some()=>"character","java/lang/Double" if self.multi_classes.is_some()=>"double","java/lang/Float" if self.multi_classes.is_some()=>"float","java/lang/Byte" if self.multi_classes.is_some()=>"byte","[Ljava/lang/reflect/Type;" if self.multi_classes.is_some()=>"ta","[Ljava/lang/String;"=>"t","java/lang/Object"=>"o","java/net/Proxy" if self.multi_classes.is_some()=>"proxy","java/net/URL" if self.multi_classes.is_some()=>"U","java/net/HttpURLConnection" if self.multi_classes.is_some()=>"httpconnection","java/lang/reflect/Type" if self.multi_classes.is_some()=>"type","java/lang/reflect/ParameterizedType" if self.multi_classes.is_some()=>"ptype","java/lang/reflect/GenericArrayType" if self.multi_classes.is_some()=>"gatype","java/lang/reflect/WildcardType" if self.multi_classes.is_some()=>"wtype","java/lang/reflect/TypeVariable" if self.multi_classes.is_some()=>"tvtype","[Ljava/lang/Object;" if self.multi_classes.is_some()=>"A","[Ljava/lang/Enum;" if self.multi_classes.is_some()=>"A","[Ljava/lang/Class;" if self.multi_classes.is_some()=>"C",_=>return Err(format!("checkcast/instanceof no soportado: {name}"))};
                        format!("builtin_instance(heap,r,{kind:?})")
                    };
                    if op==0xc0 {format!("let r=pop_r(&mut stack);if r.is_some()&&!{pred} {{raise(\"ClassCastException\",\"\");}}stack.push(V::R(r));")}
                    else {format!("let r=pop_r(&mut stack);stack.push(V::I({pred} as i32));")}
                },
                0xc4 => {
                    let child=read()?; let i=u16::from_be_bytes([read()?,read()?]) as usize;
                    match child {
                        0x15|0x16|0x19 => {
                            let t=if child==0x16 {'J'} else if child==0x19 {'i'} else {'I'};
                            if i+(if t=='J'{2}else{1})>m.locals {return Err(format!("wide load fuera de rango en {start}"));}
                            format!("stack.push(V::{}(local_{}(&locals,{i})));",variant(t),if t=='J'{"l"}else if is_ref(t){"r"}else{"i"})
                        },
                        0x36|0x37|0x3a => {
                            let t=if child==0x37 {'J'} else if child==0x3a {'i'} else {'I'};
                            if i+(if t=='J'{2}else{1})>m.locals {return Err(format!("wide store fuera de rango en {start}"));}
                            if t=='J' {format!("locals[{i}]=Some(V::L(pop_l(&mut stack))); locals[{}]=None;",i+1)}
                            else if is_ref(t) {format!("locals[{i}]=Some(V::R(pop_r(&mut stack)));")}
                            else {format!("locals[{i}]=Some(V::I(pop_i(&mut stack)));")}
                        },
                        0x84 => {
                            let inc=i16::from_be_bytes([read()?,read()?]);
                            if i>=m.locals {return Err(format!("wide iinc fuera de rango en {start}"));}
                            format!("locals[{i}]=Some(V::I(local_i(&locals,{i}).wrapping_add({inc}i32)));")
                        },
                        _=>return Err(format!("wide opcode no soportado 0x{child:02x} en offset {start}")),
                    }
                },
                0xc8 => {let delta=i32::from_be_bytes([read()?,read()?,read()?,read()?]) as i64;let dest=target(start,delta)?;branch=Some(dest);fall=false;format!("pc={dest}; continue;")},
                _=>return Err(format!("opcode numérico no soportado 0x{op:02x} en offset {start}")),
            };
            if let Some(t) = branch {
                edges.push(t);
            }
            let next = if fall {
                edges.push(pc);
                format!(" pc={pc};")
            } else {
                String::new()
            };
            arms.push_str(&format!("        {start} => {{ {body}{next} }}\n"));
        }
        if !boundaries.contains(&0) {
            return Err("código vacío".into());
        }
        for edge in edges {
            if !boundaries.contains(&edge) {
                return Err(format!("destino inválido: {edge}"));
            }
        }
        let params = sig
            .args
            .iter()
            .enumerate()
            .map(|(i, t)| format!("a{i}: {}", rt(*t)))
            .collect::<Vec<_>>()
            .join(", ");
        let this_param = if instance { ", this: usize" } else { "" };
        let heap_params = if params.is_empty() {
            format!("heap: &mut Heap{this_param}")
        } else {
            format!("heap: &mut Heap{this_param}, {params}")
        };
        let vm =
            format!("loop {{ match pc {{\n{arms}        _=>panic!(\"pc inválido\"),\n    }} }}");
        let execution = if m.handlers.is_empty() {
            vm
        } else {
            let mut checks = String::new();
            for h in &m.handlers {
                let class = h.catch_type.as_deref().unwrap_or("");
                checks.push_str(&format!("if next.is_none() && pc>={} && pc<{} && exception_matches(e.kind,{class:?}) {{next=Some({});}}\n",h.start,h.end,h.target));
            }
            format!("loop {{ let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {{ {vm} }})); match result {{ Ok(value)=>return value, Err(payload)=>{{ if let Some(e)=payload.downcast_ref::<JException>() {{ let mut next=None; {checks} if let Some(target)=next {{ let id=exception_ref(heap,e);stack.clear();stack.push(V::R(Some(id)));pc=target;continue; }} }} std::panic::resume_unwind(payload); }} }} }}")
        };
        let execution = if m.synchronized {
            if !instance {
                return Err("synchronized static no soportado".into());
            }
            format!("monitor_enter(heap,Some(this));let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{{{execution}}}));monitor_exit(heap,Some(this));match result{{Ok(v)=>v,Err(e)=>std::panic::resume_unwind(e)}}")
        } else {
            execution
        };
        let class_prefix = class_init
            .map(|i| format!("init_class_{i}(heap);\n    "))
            .unwrap_or_default();
        Ok(format!("fn {name}({heap_params}) -> {} {{\n    {class_prefix}{p}let _depth=call_guard({class:?});let mut locals: Vec<Option<V>>=vec![None; {}];\n{init}    let mut stack: Vec<V>=Vec::new();\n    let mut pc:usize=0;\n    {execution}\n}}\n",rt(sig.ret),m.locals, p = pump.unwrap_or("")))
    }
}

const RUNTIME: &str = concat!(
    include_str!("numeric_runtime.inc"),
    include_str!("unicode_casefold_java25.inc"),
    include_str!("unicode_upper_char_java25.inc"),
    include_str!("unicode_whitespace_char_java25.inc")
);

fn cli_reads(sig: &Sig) -> String {
    let mut reads = String::new();
    for (i, t) in sig.args.iter().enumerate() {
        if *t == 'T' {
            reads.push_str(&format!(
                "    let a{i}=parse_string(&mut heap, &args[{i}]);\n"
            ));
            continue;
        }
        if *t == 't' {
            reads.push_str(&format!("    let a{i}=parse_string_array(&mut heap, &args[{i}], &array_args); array_args.push(('T',a{i}));\n"));
            continue;
        }
        if is_ref(*t) {
            reads.push_str(&format!(
                "    let a{i}=parse_array(&mut heap, &args[{i}], '{}', &array_args); array_args.push(('{}',a{i}));\n",
                t.to_ascii_uppercase(), t.to_ascii_uppercase()
            ));
            continue;
        }
        reads.push_str(&format!("    let a{i}: {}=args[{i}].parse().unwrap_or_else(|_| {{eprintln!(\"argumento {i} inválido\");std::process::exit(2)}});\n",rt(*t)));
        let range = match t {
            'Z' => Some("0..=1"),
            'B' => Some("-128..=127"),
            'C' => Some("0..=65535"),
            'S' => Some("-32768..=32767"),
            _ => None,
        };
        if let Some(range) = range {
            reads.push_str(&format!("    if !({range}).contains(&a{i}) {{eprintln!(\"argumento {i} fuera del rango Java para {t}\");std::process::exit(2);}}\n"));
        }
    }
    reads
}

pub(super) fn compile_jar(jar: &Path, class: &str, method: &str, desc: &str) -> Result<String> {
    if method.starts_with('<') {
        return Err("inicializador no invocable directamente".into());
    }
    let sig = signature(desc)?;
    let data = class_from_jar(jar, class)?;
    let mut compiler = NumericCompiler {
        jar,
        class_name: class,
        class_data: &data,
        active: Vec::new(),
        compiled_methods: std::collections::HashMap::new(),
        functions: Vec::new(),
        serial: 0,
        static_fields: None,
        exception_parents: BTreeMap::new(),
        multi_classes: None,
        multi_fields: Vec::new(),
        class_literals: BTreeSet::new(),
        uses_service_loader: false,
        uses_resource_lookup: false,
        uses_enum_valueof: false,
        uses_enum_constants: false,
        interface_calls: Vec::new(),
        virtual_calls: Vec::new(),
        bootstrap_cache: BTreeMap::new(),
        lambdas: Vec::new(),
    };
    let entry = compiler.compile(class, method, desc)?;
    let is_main = method == "main" && desc == "([Ljava/lang/String;)V";
    let reads = if is_main {
        "    let a0=Some(argv_array(&mut heap,&args));\n".to_owned()
    } else {
        cli_reads(&sig)
    };
    let args = (0..sig.args.len())
        .map(|i| format!("a{i}"))
        .collect::<Vec<_>>()
        .join(", ");
    let count = sig.args.len();
    let count_check = if is_main {
        String::new()
    } else {
        format!("    if args.len()!={count} {{eprintln!(\"Se esperaban {count} argumentos\");std::process::exit(2);}}\n")
    };
    let call_args = if args.is_empty() {
        String::new()
    } else {
        format!(", {args}")
    };
    let result = if is_main {
        format!("{entry}(&mut heap{call_args});")
    } else if sig.ret == 'V' {
        format!("{entry}(&mut heap{call_args}); println!(\"OK\");")
    } else if sig.ret == 'T' {
        format!("let v={entry}(&mut heap{call_args}); println!(\"{{}}\",string_render(&heap,v));")
    } else {
        format!("println!(\"{{}}\",{entry}(&mut heap{call_args}));")
    };
    Ok(format!("// Generado por mc-aot: {class}.{method}{desc}\n#![allow(dead_code,unused_variables,unused_mut)]\n{RUNTIME}\n{}\n{}\nfn main() {{run_java(main_inner);}}\nfn main_inner() {{\n    let args:Vec<String>=std::env::args().skip(1).collect();\n{count_check}    let mut heap=Heap::default(); let mut array_args:Vec<(char,Option<usize>)>=Vec::new();\n{reads}    {result}\n}}\n",compiler.exception_parent_source(),compiler.functions.join("\n")))
}

/// A-02 fase 3 · driver de una clase vanilla **completa**.
///
/// Compila el constructor y todas las declaraciones de instancia de una clase
/// admitida por el perfil y emite un binario que ejecuta un guion de llamadas:
///
/// ```text
/// bin new 2 5 -- increment -- increment -- read count -- isUnderThreshold
/// ```
///
/// Cada paso escribe una línea: `OK` para `void`, el entero tal cual (los
/// booleanos como `1`/`0`, igual que el driver Java) y `fbits:`/`dbits:` para
/// coma flotante, que es la representación que usan las demás pruebas.
///
/// Se rechaza con motivo nombrado lo que el perfil no describe: clase no
/// pública, base distinta de `Object`, interfaces, campos estáticos, `<clinit>`,
/// campos no primitivos, `native`/`abstract` y manejadores de excepciones. No se
/// omite ninguna declaración en silencio: si el driver no sabe ejecutarla, la
/// clase entera se rechaza.
pub(super) fn class_demo_admission(jar: &Path, class: &str) -> Result<(super::metadata::Class, String)> {
    let data = class_from_jar(jar, class)?;
    let meta = super::metadata::parse(&data)?;
    if meta.name != class {
        return Err("nombre de clase no coincide con la ruta".into());
    }
    if meta.flags & 0x0001 == 0 {
        return Err(format!("clase no pública: {class}"));
    }
    if meta.flags & (0x0200 | 0x0400 | 0x4000) != 0 {
        return Err(format!("interfaz, abstracta o enum fuera del perfil: {class}"));
    }
    if meta.parent.as_deref() != Some("java/lang/Object") {
        return Err(format!("base no admitida: {:?}", meta.parent));
    }
    if !meta.interfaces.is_empty() {
        return Err(format!("interfaces fuera del perfil: {}", meta.interfaces.join(",")));
    }
    // El orden importa para el diagnóstico: 413 clases del JAR tienen estáticos
    // con `ConstantValue` y sin `<clinit>`, y 3.308 tienen inicializador.
    if meta.methods.iter().any(|m| m.name == "<clinit>") {
        return Err("inicializador estático <clinit> fuera del perfil".into());
    }
    if let Some(f) = meta.fields.iter().find(|f| f.flags & 0x0008 != 0) {
        return Err(format!("campo estático fuera del perfil: {}", f.name));
    }
    if let Some(f) = meta.fields.iter().find(|f| {
        f.flags & 0x0008 == 0 && !matches!(f.descriptor.as_str(), "I" | "J" | "F" | "D" | "Z" | "B" | "C" | "S")
    }) {
        return Err(format!(
            "campo no primitivo fuera del perfil: {} {}",
            f.name, f.descriptor
        ));
    }
    let mut seen = BTreeSet::new();
    for m in &meta.methods {
        if m.name.starts_with('<') {
            if m.name != "<init>" {
                return Err(format!("método especial no soportado: {}", m.name));
            }
            continue;
        }
        if m.flags & 0x0008 != 0 {
            return Err(format!("método estático fuera del perfil: {}", m.name));
        }
        if m.flags & (0x0100 | 0x0400) != 0 {
            return Err(format!("método native/abstract fuera del perfil: {}", m.name));
        }
        if m.exception_handlers != 0 {
            return Err(format!(
                "manejador de excepciones fuera del driver: {} {}",
                m.name, m.descriptor
            ));
        }
        if !seen.insert(m.name.clone()) {
            return Err(format!("sobrecarga fuera del driver: {}", m.name));
        }
    }
    let ctors = meta
        .methods
        .iter()
        .filter(|m| m.name == "<init>")
        .map(|m| m.descriptor.clone())
        .collect::<Vec<_>>();
    if ctors.len() != 1 {
        return Err("se requiere exactamente un constructor".into());
    }
    Ok((meta, ctors[0].clone()))
}

fn demo_arg_reads(sig: &Sig, offset: usize) -> String {
    let mut out = String::new();
    for (i, t) in sig.args.iter().enumerate() {
        let pos = i + offset;
        let rust = rt(*t);
        out.push_str(&format!(
            "            let a{i}:{rust}=step_arg(&step,{pos},\"{t}\");\n"
        ));
        let range = match t {
            'Z' => Some("0..=1"),
            'B' => Some("-128..=127"),
            'C' => Some("0..=65535"),
            'S' => Some("-32768..=32767"),
            _ => None,
        };
        if let Some(range) = range {
            out.push_str(&format!(
                "            if !({range}).contains(&a{i}) {{error(\"argumento fuera del rango Java\");}}\n"
            ));
        }
    }
    out
}

pub(super) fn compile_class_demo(jar: &Path, class: &str) -> Result<String> {
    let (meta, ctor_descriptor) = class_demo_admission(jar, class)?;
    let ctor_sig = signature_ext(&ctor_descriptor, true)?;
    let data = class_from_jar(jar, class)?;
    let mut compiler = NumericCompiler {
        jar,
        class_name: class,
        class_data: &data,
        active: Vec::new(),
        compiled_methods: std::collections::HashMap::new(),
        functions: Vec::new(),
        serial: 0,
        static_fields: None,
        exception_parents: BTreeMap::new(),
        multi_classes: Some(Vec::new()),
        multi_fields: Vec::new(),
        class_literals: BTreeSet::new(),
        uses_service_loader: false,
        uses_resource_lookup: false,
        uses_enum_valueof: false,
        uses_enum_constants: false,
        interface_calls: Vec::new(),
        virtual_calls: Vec::new(),
        bootstrap_cache: BTreeMap::new(),
        lambdas: Vec::new(),
    };
    let root = compiler.ensure_multi_class(class)?;
    let layout = compiler.instance_layout(class)?;
    if let Some(f) = layout
        .iter()
        .find(|f| !matches!(f.ty, 'I' | 'J' | 'F' | 'D' | 'Z' | 'B' | 'C' | 'S'))
    {
        return Err(format!("campo no primitivo fuera del perfil: {}", f.name));
    }
    let defaults = layout
        .iter()
        .map(|f| f.initial.clone())
        .collect::<Vec<_>>()
        .join(",");
    let ctor_fn = compiler.compile_instance(class, "<init>", &ctor_descriptor)?;
    let ctor_reads = demo_arg_reads(&ctor_sig, 1);
    let mut arms = String::new();
    let mut method_counts = Vec::new();
    for m in meta.methods.iter().filter(|m| m.name != "<init>") {
        let sig = signature_ext(&m.descriptor, true)?;
        let func = compiler.compile_instance(class, &m.name, &m.descriptor)?;
        let reads = demo_arg_reads(&sig, 1);
        let args = (0..sig.args.len())
            .map(|i| format!(",a{i}"))
            .collect::<String>();
        let call = match sig.ret {
            'V' => format!("            {func}(&mut heap,id{args});\n            println!(\"OK\");\n"),
            'F' => format!(
                "            let r={func}(&mut heap,id{args});\n            println!(\"fbits:{{:08x}}\",r.to_bits());\n"
            ),
            'D' => format!(
                "            let r={func}(&mut heap,id{args});\n            println!(\"dbits:{{:016x}}\",r.to_bits());\n"
            ),
            _ => format!("            println!(\"{{}}\",{func}(&mut heap,id{args}));\n"),
        };
        method_counts.push(m.name.clone());
        arms.push_str(&format!(
            "        {:?} => {{\n            let id=object.unwrap_or_else(||error(\"objeto no construido\"));\n{reads}{call}        }}\n",
            m.name
        ));
    }
    let mut read_arms = String::new();
    for (slot, f) in layout.iter().enumerate() {
        let render = match f.ty {
            'J' => format!("V::L(v)=>println!(\"{{}}\",v)"),
            'F' => format!("V::F(v)=>println!(\"fbits:{{:08x}}\",v.to_bits())"),
            'D' => format!("V::D(v)=>println!(\"dbits:{{:016x}}\",v.to_bits())"),
            _ => format!("V::I(v)=>println!(\"{{}}\",v)"),
        };
        read_arms.push_str(&format!(
            "{:?} => {{\n                let id=object.unwrap_or_else(||error(\"objeto no construido\"));\n                match heap.arrays.get(id) {{\n                    Some(Array::Obj(_,fields))=>match fields[{slot}]{{{render},_=>panic!(\"campo de tipo inesperado\")}},\n                    _=>error(\"objeto inexistente o de tipo inesperado\"),\n                }}\n            }}\n",
            f.name
        ));
    }
    let ctor_args = (0..ctor_sig.args.len())
        .map(|i| format!(",a{i}"))
        .collect::<String>();
    let nclasses = compiler.multi_classes.as_ref().map(|c| c.len()).unwrap_or(1);
    let source = format!(
        "// class-demo de {class}: constructor y todas las declaraciones, sin omisiones.\n\
         #![allow(dead_code,unused_variables,unused_mut)]\n{RUNTIME}\n{parents}\n{inits}\n{functions}\n\
         fn step_arg<T:std::str::FromStr>(step:&[String],i:usize,label:&str)->T{{match step.get(i).and_then(|v|v.parse::<T>().ok()){{Some(v)=>v,None=>error(&format!(\"argumento {{i}} inválido para {{label}}\"))}}}}\n\
         fn main(){{run_java(main_inner);}}\n\
         fn main_inner() {{\n\
         \x20   let raw:Vec<String>=std::env::args().skip(1).collect();\n\
         \x20   let mut steps:Vec<Vec<String>>=Vec::new();let mut cur:Vec<String>=Vec::new();\n\
         \x20   for t in raw {{ if t==\"--\" {{ if !cur.is_empty(){{steps.push(cur);cur=Vec::new();}} }} else {{ cur.push(t); }} }}\n\
         \x20   if !cur.is_empty(){{steps.push(cur);}}\n\
         \x20   if steps.is_empty(){{error(\"sin pasos: usa new y métodos separados por --\");}}\n\
         \x20   let mut heap=Heap::default();\n\
         \x20   heap.init_states=vec![0;{nclasses}];\n\
         \x20   let mut object:Option<usize>=None;\n\
         \x20   for step in steps {{\n\
         \x20       match step[0].as_str() {{\n\
         \x20           \"new\" => {{\n\
         \x20               init_class_{root}(&mut heap);\n\
         \x20               let id=object_new(&mut heap,{class:?},vec![{defaults}],false);\n\
         {ctor_reads}                {ctor_fn}(&mut heap,id{ctor_args});\n\
         \x20               object=Some(id);\n\
         \x20               println!(\"OK\");\n\
         \x20           }}\n\
         {arms}\
         \x20           \"read\" => {{\n\
         \x20               let name=step.get(1).cloned().unwrap_or_else(||error(\"read requiere un campo\"));\n\
         \x20               match name.as_str() {{\n{read_arms}\
         \x20                   _=>error(\"campo inexistente\"),\n\
         \x20               }}\n\
         \x20           }}\n\
         \x20           _=>error(\"paso desconocido\"),\n\
         \x20       }}\n\
         \x20   }}\n\
         }}\n",
        RUNTIME = RUNTIME,
        parents = compiler.exception_parent_source(),
        inits = compiler.multi_init_source(),
        functions = compiler.functions.join("\n"),
    );
    let _ = method_counts;
    Ok(source)
}

/// Genera un programa de una sola clase con sus campos estáticos y <clinit>.
/// Rechaza herencia, interfaces y campos/referencias externos para no omitir init dependientes.
pub(super) fn compile_static_demo(
    jar: &Path,
    class: &str,
    methods: &[(String, String)],
) -> Result<String> {
    if methods.is_empty() {
        return Err("se necesita al menos un método".into());
    }
    let data = class_from_jar(jar, class)?;
    let meta = super::metadata::parse(&data)?;
    if meta.name != class
        || meta.parent.as_deref() != Some("java/lang/Object")
        || !meta.interfaces.is_empty()
        || (meta.flags & 0x0200) != 0
    {
        return Err("static-demo solo admite clase directa de Object, sin interfaces".into());
    }
    let mut fields = Vec::new();
    for f in meta.fields.iter().filter(|f| f.flags & 0x0008 != 0) {
        if f.flags & 0x0040 != 0 {
            return Err(format!("campo volatile no soportado: {}", f.name));
        }
        let ty = f.descriptor.chars().next().ok_or("campo sin descriptor")?;
        if f.descriptor.len() != 1 || !"IJZBCS".contains(ty) {
            return Err(format!(
                "campo estático no primitivo soportado: {} {}",
                f.name, f.descriptor
            ));
        }
        let initial = match (ty, &f.constant) {
            ('J', None) => "V::L(0i64)".to_owned(),
            ('J', Some(super::metadata::ConstantValue::Long(v))) => format!("V::L({v}i64)"),
            ('J', Some(_)) => return Err(format!("ConstantValue incompatible: {}", f.name)),
            (_, None) => "V::I(0i32)".to_owned(),
            (_, Some(super::metadata::ConstantValue::Integer(v))) => {
                format!("V::I({})", super::return_expr(&format!("{v}i32"), ty))
            }
            (_, Some(_)) => return Err(format!("ConstantValue incompatible: {}", f.name)),
        };
        fields.push(StaticField {
            name: f.name.clone(),
            descriptor: f.descriptor.clone(),
            ty,
            initial,
            constant_string: None,
        });
    }
    let mut compiler = NumericCompiler {
        jar,
        class_name: class,
        class_data: &data,
        active: Vec::new(),
        compiled_methods: std::collections::HashMap::new(),
        functions: Vec::new(),
        serial: 0,
        static_fields: Some(fields.clone()),
        exception_parents: BTreeMap::new(),
        multi_classes: None,
        multi_fields: Vec::new(),
        class_literals: BTreeSet::new(),
        uses_service_loader: false,
        uses_resource_lookup: false,
        uses_enum_valueof: false,
        uses_enum_constants: false,
        interface_calls: Vec::new(),
        virtual_calls: Vec::new(),
        bootstrap_cache: BTreeMap::new(),
        lambdas: Vec::new(),
    };
    let clinit = if meta
        .methods
        .iter()
        .any(|m| m.name == "<clinit>" && m.descriptor == "()V")
    {
        Some(compiler.compile(class, "<clinit>", "()V")?)
    } else {
        None
    };
    let mut arms = String::new();
    for (i, (method, desc)) in methods.iter().enumerate() {
        if let Some(field) = method.strip_prefix('@') {
            let (slot, f) = fields
                .iter()
                .enumerate()
                .find(|(_, f)| f.name == field && desc.len() == 1 && desc.starts_with(f.ty))
                .ok_or_else(|| format!("campo estático no declarado: {field} {desc}"))?;
            let init_call = clinit
                .as_ref()
                .map(|f| format!("{f}(&mut heap);"))
                .unwrap_or_default();
            let pattern = if f.ty == 'J' { "L" } else { "I" };
            arms.push_str(&format!("        \"{i}\" => {{ if !initialized {{{init_call} initialized=true;}} match heap.fields[{slot}] {{ V::{pattern}(v)=>println!(\"{{}}\",v), _=>panic!(\"tipo de campo inválido\") }} }},\n"));
            continue;
        }
        if method.starts_with('<') {
            return Err("inicializador no invocable directamente".into());
        }
        let sig = signature(desc)?;
        let entry = compiler.compile(class, method, desc)?;
        let reads = cli_reads(&sig);
        let count = sig.args.len();
        let args = (0..count)
            .map(|i| format!("a{i}"))
            .collect::<Vec<_>>()
            .join(", ");
        let comma = if args.is_empty() {
            String::new()
        } else {
            format!(", {args}")
        };
        let call = if sig.ret == 'V' {
            format!("{entry}(&mut heap{comma}); println!(\"OK\");")
        } else if sig.ret == 'T' {
            format!("let v={entry}(&mut heap{comma}); println!(\"{{}}\",string_render(&heap,v));")
        } else {
            format!("println!(\"{{}}\",{entry}(&mut heap{comma}));")
        };
        let init_call = clinit
            .as_ref()
            .map(|f| format!("{f}(&mut heap);"))
            .unwrap_or_default();
        arms.push_str(&format!("        \"{i}\" => {{ if pos+{count}>input.len() {{error(\"faltan argumentos\");}} let args=&input[pos..pos+{count}]; pos+={count}; let mut array_args:Vec<(char,Option<usize>)>=Vec::new();\n{reads}            if !initialized {{{init_call} initialized=true;}} {call} }},\n"));
    }
    let initial = fields
        .iter()
        .map(|f| f.initial.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    Ok(format!("// static-demo de {class}; una clase, sin herencia ni concurrencia.\n#![allow(dead_code,unused_variables,unused_mut)]\n{RUNTIME}\n{}\n{}\nfn main() {{run_java(main_inner);}}\nfn main_inner() {{\n    let input:Vec<String>=std::env::args().skip(1).collect(); let mut pos=0; let mut initialized=false;\n    let mut heap=Heap::default(); heap.fields=vec![{initial}];\n    while pos<input.len() {{ let command=&input[pos]; pos+=1; match command.as_str() {{\n{arms}        _=>error(\"índice de método inválido\"),\n    }} }}\n}}\n",compiler.exception_parent_source(),compiler.functions.join("\n")))
}

/// Experimento monohilo con clases directas de Object y campos estáticos primitivos.
/// Rechaza handlers: un fallo de inicialización termina el proceso, no se simula erróneamente.
pub(super) fn compile_multi_static_demo(
    jar: &Path,
    class: &str,
    methods: &[(String, String)],
) -> Result<String> {
    compile_multi_static_inner(jar, class, methods, None)
}
pub(super) fn compile_shared_worker_demo(
    jar: &Path,
    class: &str,
    methods: &[(String, String)],
    plan: &super::shared_worker::Plan,
) -> Result<String> {
    if methods.len()!=2 || methods.iter().any(|(_,d)|d!="(I)I") {return Err("worker compartido: requiere tick y lectura (I)I".into());}
    compile_multi_static_inner(jar, class, methods, Some(plan))
}
fn compile_multi_static_inner(
    jar: &Path,
    class: &str,
    methods: &[(String, String)],
    worker: Option<&super::shared_worker::Plan>,
) -> Result<String> {
    if methods.is_empty() {
        return Err("se necesita al menos un método".into());
    }
    let data = class_from_jar(jar, class)?;
    let mut compiler = NumericCompiler {
        jar,
        class_name: class,
        class_data: &data,
        active: Vec::new(),
        compiled_methods: std::collections::HashMap::new(),
        functions: Vec::new(),
        serial: 0,
        static_fields: None,
        exception_parents: BTreeMap::new(),
        multi_classes: Some(Vec::new()),
        multi_fields: Vec::new(),
        class_literals: BTreeSet::new(),
        uses_service_loader: false,
        uses_resource_lookup: false,
        uses_enum_valueof: false,
        uses_enum_constants: false,
        interface_calls: Vec::new(),
        virtual_calls: Vec::new(),
        bootstrap_cache: BTreeMap::new(),
        lambdas: Vec::new(),
    };
    let root = compiler.ensure_multi_class(class)?;
    let mut arms = String::new();
    let mut worker_entries=Vec::new();
    for (i, (method, desc)) in methods.iter().enumerate() {
        if let Some(field) = method.strip_prefix('@') {
            let (slot, f) = compiler.multi_classes.as_ref().unwrap()[root]
                .fields
                .iter()
                .find(|(_, f)| f.name == field && f.descriptor == *desc)
                .ok_or_else(|| format!("campo estático no declarado: {field} {desc}"))?;
            let render = if f.ty == 'F' {
                "V::F(v)=>println!(\"fbits:{:08x}\",v.to_bits())".to_owned()
            } else if f.ty == 'D' {
                "V::D(v)=>println!(\"dbits:{:016x}\",v.to_bits())".to_owned()
            } else if matches!(f.ty, 'f' | 'd') {
                return Err("lectura CLI de float[]/double[] no soportada".into());
            } else if f.ty == 'T' {
                "V::R(v)=>println!(\"{}\",string_render(&heap,v))".to_owned()
            } else if matches!(f.ty, 'o' | 'a') {
                return Err(
                    "lectura CLI de objeto o array de objetos no soportada; usa un método".into(),
                );
            } else if is_ref(f.ty) {
                "V::R(v)=>println!(\"{}\",array_render(&heap,v))".to_owned()
            } else {
                let p = if f.ty == 'J' { "L" } else { "I" };
                format!("V::{p}(v)=>println!(\"{{}}\",v)")
            };
            arms.push_str(&format!("        {i:?} => {{init_class_{root}(&mut heap); match heap.fields[{slot}] {{{render},_=>panic!(\"tipo de campo inválido\")}}}},\n"));
            continue;
        }
        if method.starts_with('<') {
            return Err("inicializador no invocable directamente".into());
        }
        let sig = signature(desc)?;
        let entry = compiler.compile(class, method, desc)?;
        if worker.is_some() {worker_entries.push(entry.clone());}
        let reads = cli_reads(&sig);
        let count = sig.args.len();
        let args = (0..count)
            .map(|i| format!("a{i}"))
            .collect::<Vec<_>>()
            .join(", ");
        let comma = if args.is_empty() {
            String::new()
        } else {
            format!(", {args}")
        };
        let call = if sig.ret == 'V' {
            format!("{entry}(&mut heap{comma});println!(\"OK\");")
        } else if sig.ret == 'T' {
            format!("let v={entry}(&mut heap{comma});println!(\"{{}}\",string_render(&heap,v));")
        } else {
            format!("println!(\"{{}}\",{entry}(&mut heap{comma}));")
        };
        arms.push_str(&format!("        {i:?} => {{if pos+{count}>input.len() {{error(\"faltan argumentos\");}} let args=&input[pos..pos+{count}];pos+={count};let mut array_args:Vec<(char,Option<usize>)>=Vec::new();\n{reads} {call}}},\n"));
    }
    // CLI commands are strings, not numeric match patterns.
    for i in 0..methods.len() {
        arms = arms.replace(&format!("        {i} =>"), &format!("        \"{i}\" =>"));
    }
    // Se registran explícitamente tipos para reflexión: no se inventa un constructor.
    let mut registry = Vec::new();
    let mut declared_registry = Vec::new();
    let mut ctor_modifiers = Vec::new();
    let mut arms_reflect = String::new();
    let mut seen = BTreeSet::new();
    let requested = std::env::var("MC_AOT_REFLECT_CLASSES").unwrap_or_default();
    for class in requested.split(':').filter(|x| !x.is_empty()) {
        if !seen.insert(class.to_owned()) {
            return Err(format!("clase reflectiva duplicada: {class}"));
        }
        let data = class_from_jar(jar, class)?;
        let meta = super::metadata::parse(&data)?;
        if meta.name != class
            || meta.flags & 0x0001 == 0
            || meta.flags & (0x0200 | 0x0400 | 0x4000) != 0
        {
            return Err(format!(
                "reflexión requiere clase pública concreta no enum: {class}"
            ));
        }
        let id = compiler.ensure_multi_class(class)?;
        let constructor = meta
            .methods
            .iter()
            .any(|m| m.name == "<init>" && m.descriptor == "()V" && m.flags & 0x0001 != 0);
        registry.push(format!("({class:?},{constructor})"));
        if constructor {
            let flags=meta.methods.iter().find(|m|m.name=="<init>"&&m.descriptor=="()V"&&m.flags&1!=0).unwrap().flags;
            ctor_modifiers.push(format!("({class:?},{}i32)",flags));
        }
        let declared = meta
            .methods
            .iter()
            .any(|m| m.name == "<init>" && m.descriptor == "()V");
        declared_registry.push(format!("({class:?},{constructor},{declared})"));
        if constructor {
            let fields = compiler.instance_layout(class)?;
            let defaults = fields
                .iter()
                .map(|f| f.initial.as_str())
                .collect::<Vec<_>>()
                .join(",");
            let local = compiler.multi_classes.as_ref().unwrap()[id].inheritable_local;
            let func = compiler.compile_instance(class, "<init>", "()V")?;
            arms_reflect.push_str(&format!("{class:?}=>{{init_class_{id}(heap);let id=object_new(heap,{class:?},vec![{defaults}],{local});let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{func}(heap,id)));match result{{Ok(())=>Some(id),Err(p)=>wrap_invocation(heap,p)}}}},"));
        }
    }
    let reflection_source=format!("const REFLECT_CTORS:&[(&str,bool)]=&[{}];\nconst REFLECT_DECLARED_CTORS:&[(&str,bool,bool)]=&[{}];\nconst REFLECT_CTOR_MODIFIERS:&[(&str,i32)]=&[{}];\nfn reflect_construct(heap:&mut Heap,ctor:Option<usize>,args:Option<usize>)->Option<usize>{{let class=reflect_ctor_class(heap,ctor,args);match class{{{arms_reflect}_=>error(\"Constructor.newInstance: clase no registrada\")}}}}",registry.join(","),declared_registry.join(","),ctor_modifiers.join(","));
    // Registro explícito de métodos públicos directos, instancia, cero o un
    // parámetro de proyecto, retorno void/referencia. No adivina métodos ausentes.
    let requested_methods = std::env::var("MC_AOT_REFLECT_METHODS").unwrap_or_default();
    let mut method_registry = Vec::new();
    let mut method_modifiers = Vec::new();
    let mut method_arms = String::new();
    let mut method_seen = BTreeSet::new();
    for entry in requested_methods.split('|').filter(|x| !x.is_empty()) {
        let parts = entry.split('#').collect::<Vec<_>>();
        if parts.len() != 3 {
            return Err(
                "MC_AOT_REFLECT_METHODS requiere clase#nombre#descriptor separados por |".into(),
            );
        }
        let (class, name, desc) = (parts[0], parts[1], parts[2]);
        let end = desc.find(')').ok_or("descriptor reflectivo inválido")?;
        if !desc.starts_with('(') || end == 0 {
            return Err("descriptor reflectivo inválido".into());
        }
        let params = &desc[1..end];
        let ret = &desc[end + 1..];
        let param = if params.is_empty() {
            ""
        } else if params.starts_with('L')
            && params.ends_with(';')
            && !params[1..params.len() - 1].contains(';')
        {
            &params[1..params.len() - 1]
        } else {
            return Err(format!("parámetros reflectivos no soportados: {desc}"));
        };
        if !desc.starts_with('(')
            || !(ret == "V" || (ret.starts_with('L') && ret.ends_with(';')))
            || (!param.is_empty() && !project_class(param))
        {
            return Err(format!("firma reflectiva no soportada: {desc}"));
        }
        if !method_seen.insert((class.to_owned(), name.to_owned(), params.to_owned())) {
            return Err(format!("método reflectivo duplicado: {entry}"));
        }
        let data = class_from_jar(jar, class)?;
        let meta = super::metadata::parse(&data)?;
        if meta.name != class || meta.flags & 0x0001 == 0 || meta.flags & (0x0200 | 0x0400) != 0 {
            return Err(format!(
                "reflexión de método requiere clase pública concreta: {class}"
            ));
        }
        let matching = meta
            .methods
            .iter()
            .filter(|m| {
                m.name == name
                    && m.descriptor.starts_with(&format!("({params})"))
                    && m.flags & 0x0001 != 0
                    && m.flags & 0x0008 == 0
            })
            .collect::<Vec<_>>();
        if matching.len() != 1 || matching[0].descriptor != desc {
            return Err(format!(
                "método reflectivo no es público directo único: {entry}"
            ));
        }
        if !param.is_empty() {
            compiler.verify_project_cast_target(param)?;
        }
        let f = compiler.compile_instance(class, name, desc)?;
        let index = method_registry.len();
        method_registry.push(format!("({class:?},{name:?},{param:?})"));
        method_modifiers.push(format!("{}i32",matching[0].flags));
        let (check, argument) = if param.is_empty() {
            (
                "reflect_check_count(heap,args,0);".to_owned(),
                "".to_owned(),
            )
        } else {
            (format!("reflect_check_count(heap,args,1);let arg=reflect_argument(heap,args,{param:?},PROJECT_INTERFACES);"),",arg".to_owned())
        };
        let run = if ret == "V" {
            format!("{f}(heap,id{argument});None")
        } else {
            format!("{f}(heap,id{argument})")
        };
        method_arms.push_str(&format!("{index}=>{{let id=reflect_receiver(heap,receiver,{class:?});{check}let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{{{run}}}));match result{{Ok(v)=>v,Err(p)=>wrap_invocation(heap,p)}}}},"));
    }
    let methods_source=format!("const REFLECT_METHODS:&[(&str,&str,&str)]=&[{}];\nconst REFLECT_METHOD_MODIFIERS:&[i32]=&[{}];\nfn reflect_invoke(heap:&mut Heap,method:Option<usize>,receiver:Option<usize>,args:Option<usize>)->Option<usize>{{let idx=reflect_method_index(heap,method);match idx{{{method_arms}_=>error(\"Method.invoke: método no registrado\")}}}}",method_registry.join(","),method_modifiers.join(","));
    let dispatch_source = compiler.interface_dispatch_source()?;
    let initial = compiler
        .multi_fields
        .iter()
        .map(|f| f.initial.as_str())
        .collect::<Vec<_>>()
        .join(", ");
    let nclasses = compiler.multi_classes.as_ref().unwrap().len();
    let binder_present = if compiler.uses_resource_lookup {
        super::classpath::has_class(jar, "org/slf4j/impl/StaticLoggerBinder")?
    } else {
        false
    };
    let provider_absent = compiler.uses_resource_lookup
        && std::env::var_os("MC_AOT_CLOSED_CLASSPATH").as_deref()
            == Some(std::ffi::OsStr::new("1"))
        && super::classpath::require_absent_resource(jar, "META-INF/log4j-provider.properties")
            .is_ok();
    let resource_source = format!("const STATIC_BINDER_PRESENT:bool={binder_present};const LOG4J_PROVIDER_ABSENT:bool={provider_absent};");
    let service_table = if compiler.uses_service_loader {
        let mut items = Vec::new();
        for (service, resources) in super::classpath::services(jar)? {
            let providers = parse_service_resources(&resources);
            let list = providers
                .iter()
                .map(|s| format!("{s:?}"))
                .collect::<Vec<_>>()
                .join(",");
            items.push(format!("({service:?},&[{list}])"));
        }
        format!(
            "const SERVICE_CATALOG:&[(&str,&[&str])]=&[{}];",
            items.join(",")
        )
    } else {
        "const SERVICE_CATALOG:&[(&str,&[&str])]=&[];".to_owned()
    };
    let mut interface_pairs = Vec::new();
    for c in compiler.multi_classes.as_ref().unwrap() {
        for interface in compiler.class_interfaces(&c.name)? {
            interface_pairs.push(format!("({:?},{interface:?})", c.name));
        }
        let mut cursor = c.parent;
        while let Some(p) = cursor {
            let parent = &compiler.multi_classes.as_ref().unwrap()[p];
            interface_pairs.push(format!("({:?},{:?})", c.name, parent.name));
            cursor = parent.parent;
        }
    }
    for literal in &compiler.class_literals {
        if project_class(literal) && !literal.starts_with('[') {
            let data = class_from_jar(jar, literal)?;
            let meta = super::metadata::parse(&data)?;
            if meta.flags & 0x0200 != 0 {
                for parent in compiler.interface_closure(&meta.interfaces)? {
                    interface_pairs.push(format!("({literal:?},{parent:?})"));
                }
            }
        }
    }
    for lambda in &compiler.lambdas {
        if project_class(&lambda.interface) {
            let data = class_from_jar(jar, &lambda.interface)?;
            let meta = super::metadata::parse(&data)?;
            for parent in compiler.interface_closure(&meta.interfaces)? {
                interface_pairs.push(format!("({:?},{parent:?})", lambda.interface));
            }
        }
    }
    let parent_pairs = compiler
        .multi_classes
        .as_ref()
        .unwrap()
        .iter()
        .filter_map(|c| {
            c.parent.map(|p| {
                format!(
                    "({:?},{:?})",
                    c.name,
                    compiler.multi_classes.as_ref().unwrap()[p].name
                )
            })
        })
        .collect::<Vec<_>>()
        .join(",");
    let parent_count = compiler
        .multi_classes
        .as_ref()
        .unwrap()
        .iter()
        .filter(|c| c.parent.is_some())
        .count();
    let interface_table = format!(
        "const PROJECT_INTERFACES:&[(&str,&str)]=&[{}];",
        interface_pairs.join(",")
    );
    let mut known = compiler.class_literals.clone();
    known.extend(
        compiler
            .multi_classes
            .as_ref()
            .unwrap()
            .iter()
            .map(|c| c.name.clone()),
    );
    let entries = known
        .iter()
        .map(|s| format!("({:?},{:?})", s.replace('/', "."), s))
        .collect::<Vec<_>>()
        .join(",");
    let project_types = known
        .iter()
        .filter(|s| project_class(s) && !s.starts_with('['))
        .map(|s| format!("{s:?}"))
        .collect::<Vec<_>>()
        .join(",");
    let mut interface_classes = Vec::new();
    let mut project_modifiers = Vec::new();
    for name in &known {
        if project_class(name) && !name.starts_with('[') {
            let data = class_from_jar(jar, name)?;
            let meta=super::metadata::parse(&data)?;
            if meta.flags & 0x0200 != 0 {
                interface_classes.push(format!("{name:?}"));
            }
            let modifiers=meta.inner_flags.unwrap_or(meta.flags)&!0x0020;
            project_modifiers.push(format!("({name:?},{modifiers}i32)"));
        }
    }
    let types_source = format!("const PROJECT_TYPES:&[&str]=&[{project_types}];const PROJECT_INTERFACE_CLASSES:&[&str]=&[{}];const PROJECT_CLASS_MODIFIERS:&[(&str,i32)]=&[{}];",interface_classes.join(","),project_modifiers.join(","));
    let init_cases = compiler
        .multi_classes
        .as_ref()
        .unwrap()
        .iter()
        .enumerate()
        .map(|(id, c)| format!("{:?}=>init_class_{id}(heap),", c.name))
        .collect::<String>();
    // Perfil conservador: únicamente el values() canónico de javac, con $VALUES
    // privado static final synthetic. Otros enums se rechazan al ejecutarse.
    let mut enum_cases=String::new();
    let mut enum_const_cases=String::new();
    if compiler.uses_enum_valueof || compiler.uses_enum_constants {
        for (id,c) in compiler.multi_classes.as_ref().unwrap().iter().enumerate() {
            let bytes=class_from_jar(jar,&c.name)?;
            let meta=super::metadata::parse(&bytes)?;
            if meta.flags & 0x4000 == 0 || meta.parent.as_deref()!=Some("java/lang/Enum") {continue;}
            let arr=format!("[L{};",c.name);let values_desc=format!("(){arr}");
            let Some(field)=meta.fields.iter().find(|f|f.name=="$VALUES" && f.descriptor==arr && f.flags & 0x101a==0x101a) else {continue;};
            if !meta.methods.iter().any(|m|m.name=="values" && m.descriptor==values_desc && m.flags & 0x0009==0x0009) {continue;}
            let Ok(m)=super::find_method_inner(&bytes,"values",&values_desc,false,true,false) else {continue;};
            let b=&m.code;
            if b.len()!=10 || b[0]!=0xb2 || b[3]!=0xb6 || b[6]!=0xc0 || b[9]!=0xb0 {continue;}
            let ix=|i|u16::from_be_bytes([b[i],b[i+1]]);
            if super::object::field_ref(&m.cp,ix(1)).ok()!=Some((c.name.as_str(),field.name.as_str(),field.descriptor.as_str())) {continue;}
            if super::method_ref(&m.cp,ix(4)).ok()!=Some((arr.as_str(),"clone","()Ljava/lang/Object;")) {continue;}
            let cast=match m.cp.get(ix(7) as usize){Some(super::CpEntry::Class(i))=>super::utf(&m.cp,*i).ok(),_=>None};
            if cast!=Some(arr.as_str()){continue;}
            let Some((slot,_))=c.fields.iter().find(|(_,f)|f.name=="$VALUES"&&f.descriptor==arr) else {continue;};
            let canonical=if c.name.contains('$'){"None".to_owned()}else{format!("Some({:?})",c.name.replace('/',"."))};
            if compiler.uses_enum_valueof {enum_cases.push_str(&format!("{:?}=>{{init_class_{id}(heap);enum_valueof_array(heap,target,name,{slot},{canonical})}},",c.name));}
            if compiler.uses_enum_constants {enum_const_cases.push_str(&format!("{:?}=>{{init_class_{id}(heap);enum_constants_array(heap,{slot},{:?})}},",c.name,c.name));}
        }
    }
    let valueof_fn=if compiler.uses_enum_valueof {format!("fn enum_valueof(heap:&mut Heap,class:Option<usize>,name:Option<usize>)->Option<usize>{{let id=array_id(heap,class);let target=match heap.arrays[id]{{Array::Class(n)=>n,_=>error(\"Enum.valueOf: Class fuera del perfil\")}};match target{{{enum_cases}_=>error(\"Enum.valueOf: clase fuera del perfil\")}}}} ")}else{String::new()};
    let constants_fn=if compiler.uses_enum_constants {format!("fn enum_constants(heap:&mut Heap,class:Option<usize>)->Option<usize>{{let id=array_id(heap,class);let target=match heap.arrays[id]{{Array::Class(n)=>n,_=>error(\"Class.getEnumConstants: receptor no es una clase\")}};match target{{{enum_const_cases}_=>None}}}}")}else{"fn enum_constants(_heap:&mut Heap,class:Option<usize>)->Option<usize>{let _=class;None}".to_owned()};
    let enum_source=format!("{valueof_fn}{constants_fn}\n");
    let loader_table = format!("const PRECOMPILED_CLASSES:&[(&str,&str)]=&[{entries}];\nfn class_for_name_three(heap:&mut Heap,name:Option<usize>,initialize:i32,loader:Option<usize>)->usize{{string_units(heap,name);if loader.is_none(){{error(\"Class.forName: loader bootstrap fuera del perfil\");}}let class=classloader_load(heap,loader,name,PRECOMPILED_CLASSES);let target=match heap.arrays[class]{{Array::Class(n)=>n,_=>unreachable!()}};if [\"java/\",\"javax/\",\"jdk/\",\"sun/\",\"com/sun/\"].iter().any(|p|target.starts_with(p))||target.starts_with('['){{error(\"Class.forName: solo clases de proyecto precompiladas\");}}if initialize!=0{{match target{{{init_cases}_=>error(\"Class.forName: inicialización no precompilada\")}}}}class}}");
    if let Some(plan)=worker {
        let descriptor=format!("L{};",plan.target_class);
        let (slot,_)=compiler.multi_classes.as_ref().unwrap()[root].fields.iter().find(|(_,f)|f.name==plan.static_field && f.descriptor==descriptor).ok_or("worker compartido: static no registrado")?;
        let tick=&worker_entries[0];let read=&worker_entries[1];let target=&plan.target_class;let delta=plan.delta;
        let (wrapper,task_entry)=match plan.wrapper {
            super::shared_worker::WorkerWrapper::None=>("","task_run_aot"),
            super::shared_worker::WorkerWrapper::Util4=>("fn util4_run_aot(obj:&NumericObjectHandle){task_run_aot(obj);}","util4_run_aot"),
            super::shared_worker::WorkerWrapper::TickTask=>("fn ticktask_run_aot(obj:&NumericObjectHandle){task_run_aot(obj);}","ticktask_run_aot"),
        };
        // La tarea estática fue validada byte por byte en shared_worker::verify.
        // `run` y el método synchronized del destino son traducidos al helper;
        // el objeto Runnable no escapa y no se materializa en este perfil.
        return Ok(format!("// shared-worker-demo acotado; no es ForkJoinPool Java general.\n#![allow(dead_code,unused_variables,unused_mut)]\n{RUNTIME}\n{enum_source}\n{loader_table}\n{types_source}\n{interface_table}\n{resource_source}\n{service_table}\n{reflection_source}\n{methods_source}\n{dispatch_source}\n{}\n{}\n{}\nfn task_run_aot(obj:&NumericObjectHandle){{let _guard=obj.enter_monitor().unwrap_or_else(|e|error(e));let old=obj.read_int(0).unwrap_or_else(|e|error(e));obj.write_int(0,old.wrapping_add({delta}i32)).unwrap_or_else(|e|error(e));}}\n{wrapper}\nfn main(){{run_java(main_inner);}}\nfn main_inner(){{let args:Vec<String>=std::env::args().skip(1).collect();if args.len()!=1{{error(\"uso: binario repeticiones (0..=10000)\");}}let n:usize=args[0].parse().unwrap_or_else(|_|error(\"repeticiones inválidas\"));if n>10000{{error(\"repeticiones fuera de perfil\");}}let mut heap=Heap::default();heap.interfaces=PROJECT_INTERFACES;heap.fields=vec![{initial}];heap.init_states=vec![0;{nclasses}];heap.parents.extend::<[(&'static str,&'static str); {parent_count}]>([{parent_pairs}]);init_class_{root}(&mut heap);let id=match heap.fields[{slot}]{{V::R(Some(id))=>id,_=>error(\"worker compartido: static null o inválido\")}};match heap.arrays.get(id){{Some(Array::Obj(c,_)) if *c=={target:?}=>(),_=>error(\"worker compartido: tipo destino inesperado\")}}let target=share_project_object(&mut heap,id).unwrap_or_else(|e|error(e));let pool=rayon::ThreadPoolBuilder::new().num_threads(4).build().unwrap_or_else(|_|error(\"worker compartido: no se pudo crear pool\"));let gate=std::sync::Arc::new(std::sync::Barrier::new(5));let(tx,rx)=std::sync::mpsc::channel();for _ in 0..4{{let o=target.clone();let tx=tx.clone();let gate=gate.clone();pool.spawn(move||{{let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||{{gate.wait();for _ in 0..n{{{task_entry}(&o);}}}}));let _=tx.send(result.is_ok());}});}}drop(tx);gate.wait();for _ in 0..n{{{tick}(&mut heap,0);}}for _ in 0..4{{if rx.recv()!=Ok(true){{error(\"worker compartido: tarea falló\");}}}}println!(\"{{}}\",{read}(&mut heap,0));}}\n",compiler.exception_parent_source(),compiler.multi_init_source(),compiler.functions.join("\n")));
    }
    Ok(format!("// multi-static-demo de {class}; inicialización acotada, monohilo.\n#![allow(dead_code,unused_variables,unused_mut)]\n{RUNTIME}\n{enum_source}\n{loader_table}\n{types_source}\n{interface_table}\n{resource_source}\n{service_table}\n{reflection_source}\n{methods_source}\n{dispatch_source}\n{}\n{}\n{}\nfn main() {{run_java(main_inner);}}\nfn main_inner() {{\n let input:Vec<String>=std::env::args().skip(1).collect();let mut pos=0;let mut heap=Heap::default();heap.interfaces=PROJECT_INTERFACES;heap.fields=vec![{initial}];heap.init_states=vec![0;{nclasses}];heap.parents.extend::<[(&'static str,&'static str); {parent_count}]>([{parent_pairs}]);\n while pos<input.len() {{let command=&input[pos];pos+=1;match command.as_str() {{\n{arms} _=>error(\"índice de método inválido\"),\n}}}}\n}}\n",compiler.exception_parent_source(),compiler.multi_init_source(),compiler.functions.join("\n")))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn security_method(code: Vec<u8>) -> Method {
        fn text(s: &str) -> super::super::JavaUtf8 {
            super::super::JavaUtf8 {
                units: s.encode_utf16().collect(),
                text: Some(s.to_owned()),
            }
        }
        Method {
            code,
            locals: 1,
            handlers: vec![],
            synchronized: false,
            cp: vec![
                CpEntry::Empty,
                CpEntry::MethodRef(2, 4),
                CpEntry::Class(3),
                CpEntry::Utf8(text("java/lang/System")),
                CpEntry::NameType(5, 6),
                CpEntry::Utf8(text("getSecurityManager")),
                CpEntry::Utf8(text("()Ljava/lang/SecurityManager;")),
            ],
        }
    }
    #[test]
    fn security_fold_requires_unique_entries() {
        let mut m = security_method(vec![
            0xb8, 0, 1, 0x4b, 0x2a, 0xc7, 0, 5, 0x04, 0xac, 0xba, 0, 0, 0, 0, 0x05, 0xac,
        ]);
        let reachable = profile_reachable(&m).unwrap().unwrap();
        assert!(reachable.contains(&8));
        assert!(!reachable.contains(&10));
        m.handlers.push(super::super::ExceptionHandler {
            start: 0,
            end: 3,
            target: 4,
            catch_type: None,
        });
        assert!(profile_reachable(&m).unwrap().is_none());
        let m = security_method(vec![
            0xa7, 0, 7, 0xb8, 0, 1, 0x4b, 0x2a, 0xc7, 0, 5, 0x04, 0xac, 0x05, 0xac,
        ]);
        assert!(profile_reachable(&m).unwrap().is_none());
    }
    #[test]
    fn descriptors() {
        let s = signature("(IJZ)J").unwrap();
        assert_eq!(s.args, vec!['I', 'J', 'Z']);
        assert_eq!(s.ret, 'J');
        assert_eq!(signature("([I[JZ)I").unwrap().args, vec!['i', 'j', 'Z']);
        assert!(signature("([[I)I").is_err());
        assert_eq!(
            signature("([Ljava/lang/String;Ljava/lang/String;)I")
                .unwrap()
                .args,
            vec!['t', 'T']
        );
        assert!(signature("(D)J").is_err());
        assert_eq!(signature("(J)V").unwrap().ret, 'V');
    }
    #[test]
    fn signed_targets() {
        assert_eq!(target(20, -7).unwrap(), 13);
        assert!(target(2, -7).is_err());
    }
}
