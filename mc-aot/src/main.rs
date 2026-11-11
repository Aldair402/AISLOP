#[allow(dead_code)]
mod class_init;
#[allow(dead_code)]
mod concurrent_classes;
mod concurrent_compile;
#[allow(dead_code)]
mod concurrent_heap;
mod executor_runtime;
#[allow(dead_code)]
mod forkjoin;
#[allow(dead_code)]
mod frame_vm;
#[allow(dead_code)]
mod rayon_scheduler;
#[allow(dead_code)]
mod scheduler;
mod split_source;
use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

type Result<T> = std::result::Result<T, String>;
mod bytecode;
mod classpath;
use classpath::class_from_jar;
mod flow;
mod metadata;
mod multi;
mod numeric;
mod shared_worker;
mod object;
mod reference;

struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
}
impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8]> {
        let end = self.pos.checked_add(n).ok_or("desbordamiento al leer")?;
        let part = self
            .data
            .get(self.pos..end)
            .ok_or("archivo .class truncado")?;
        self.pos = end;
        Ok(part)
    }
    fn u1(&mut self) -> Result<u8> {
        Ok(self.take(1)?[0])
    }
    fn u2(&mut self) -> Result<u16> {
        let b = self.take(2)?;
        Ok(u16::from_be_bytes([b[0], b[1]]))
    }
    fn u4(&mut self) -> Result<u32> {
        let b = self.take(4)?;
        Ok(u32::from_be_bytes([b[0], b[1], b[2], b[3]]))
    }
}
#[derive(Clone, Debug)]
enum CpEntry {
    Empty,
    Utf8(JavaUtf8),
    Integer(i32),
    FloatBits(u32),
    Long(i64),
    DoubleBits(u64),
    String(u16),
    Class(u16),
    NameType(u16, u16),
    MethodRef(u16, u16),
    InterfaceMethodRef(u16, u16),
    FieldRef(u16, u16),
    MethodType(u16),
    MethodHandle(u8, u16),
    InvokeDynamic(u16, u16),
}
#[derive(Clone, Debug)]
struct JavaUtf8 {
    // JVM strings may contain unpaired UTF-16 surrogates. Keep the original code units.
    #[allow(dead_code)]
    units: Vec<u16>,
    text: Option<String>,
}
impl JavaUtf8 {
    fn decode(data: &[u8]) -> Result<Self> {
        let mut units = Vec::new();
        let mut p = 0;
        while p < data.len() {
            let a = data[p];
            p += 1;
            let unit = match a {
                0x01..=0x7f => a as u16,
                0xc0..=0xdf => {
                    let b = *data.get(p).ok_or("MUTF-8 truncado")?;
                    p += 1;
                    if b & 0xc0 != 0x80 {
                        return Err("continuación MUTF-8 inválida".into());
                    }
                    let v = ((a as u16 & 0x1f) << 6) | (b as u16 & 0x3f);
                    if v < 0x80 && !(a == 0xc0 && b == 0x80) {
                        return Err("MUTF-8 sobrelargo".into());
                    }
                    v
                }
                0xe0..=0xef => {
                    let b = *data.get(p).ok_or("MUTF-8 truncado")?;
                    let c = *data.get(p + 1).ok_or("MUTF-8 truncado")?;
                    p += 2;
                    if b & 0xc0 != 0x80 || c & 0xc0 != 0x80 {
                        return Err("continuación MUTF-8 inválida".into());
                    }
                    let v =
                        ((a as u16 & 0x0f) << 12) | ((b as u16 & 0x3f) << 6) | (c as u16 & 0x3f);
                    if v < 0x800 {
                        return Err("MUTF-8 sobrelargo".into());
                    }
                    v
                }
                _ => return Err(format!("byte MUTF-8 inválido 0x{a:02x}")),
            };
            units.push(unit);
        }
        let text = String::from_utf16(&units).ok();
        Ok(Self { units, text })
    }
}
fn utf(cp: &[CpEntry], index: u16) -> Result<&str> {
    match cp.get(index as usize) {
        Some(CpEntry::Utf8(s)) => s
            .text
            .as_deref()
            .ok_or_else(|| format!("UTF-16 no válido para nombre/descriptor: {index}")),
        _ => Err(format!("índice UTF8 inválido: {index}")),
    }
}
fn method_ref(cp: &[CpEntry], index: u16) -> Result<(&str, &str, &str)> {
    let (class_idx, nt_idx) = match cp.get(index as usize) {
        Some(CpEntry::MethodRef(c, n)) | Some(CpEntry::InterfaceMethodRef(c, n)) => (*c, *n),
        _ => return Err(format!("Methodref inválido: {index}")),
    };
    let class_name = match cp.get(class_idx as usize) {
        Some(CpEntry::Class(n)) => utf(cp, *n)?,
        _ => return Err("Class inválida".into()),
    };
    let (name, desc) = match cp.get(nt_idx as usize) {
        Some(CpEntry::NameType(n, d)) => (utf(cp, *n)?, utf(cp, *d)?),
        _ => return Err("NameAndType inválido".into()),
    };
    Ok((class_name, name, desc))
}
fn skip_attrs(r: &mut Reader<'_>) -> Result<()> {
    let count = r.u2()?;
    for _ in 0..count {
        r.u2()?;
        let len = r.u4()? as usize;
        r.take(len)?;
    }
    Ok(())
}
#[derive(Debug)]
struct ExceptionHandler {
    start: usize,
    end: usize,
    target: usize,
    catch_type: Option<String>,
}
struct Method {
    code: Vec<u8>,
    locals: usize,
    cp: Vec<CpEntry>,
    handlers: Vec<ExceptionHandler>,
    synchronized: bool,
}
fn read_cp(r: &mut Reader<'_>) -> Result<Vec<CpEntry>> {
    let n = r.u2()? as usize;
    if n == 0 {
        return Err("constant pool vacío".into());
    }
    let mut cp: Vec<CpEntry> = vec![CpEntry::Empty; n];
    let mut i = 1;
    while i < n {
        match r.u1()? {
            1 => {
                let len = r.u2()? as usize;
                let s = r.take(len)?;
                cp[i] = CpEntry::Utf8(JavaUtf8::decode(s)?);
            }
            3 => {
                cp[i] = CpEntry::Integer(r.u4()? as i32);
            }
            4 => {
                cp[i] = CpEntry::FloatBits(r.u4()?);
            }
            tag @ (5 | 6) => {
                let bytes = r.take(8)?;
                if tag == 5 {
                    cp[i] = CpEntry::Long(i64::from_be_bytes(bytes.try_into().unwrap()));
                } else {
                    cp[i] = CpEntry::DoubleBits(u64::from_be_bytes(bytes.try_into().unwrap()));
                }
                i += 1;
                if i >= n {
                    return Err("constant pool inválido".into());
                }
            }
            7 => {
                cp[i] = CpEntry::Class(r.u2()?);
            }
            16 => {
                cp[i] = CpEntry::MethodType(r.u2()?);
            }
            8 => {
                cp[i] = CpEntry::String(r.u2()?);
            }
            19 | 20 => {
                r.take(2)?;
            }
            10 => {
                cp[i] = CpEntry::MethodRef(r.u2()?, r.u2()?);
            }
            12 => {
                cp[i] = CpEntry::NameType(r.u2()?, r.u2()?);
            }
            9 => {
                cp[i] = CpEntry::FieldRef(r.u2()?, r.u2()?);
            }
            11 => {
                cp[i] = CpEntry::InterfaceMethodRef(r.u2()?, r.u2()?);
            }
            17 => {
                r.take(4)?;
            }
            18 => {
                cp[i] = CpEntry::InvokeDynamic(r.u2()?, r.u2()?);
            }
            15 => {
                cp[i] = CpEntry::MethodHandle(r.u1()?, r.u2()?);
            }
            t => return Err(format!("tipo constant pool no soportado: {t}")),
        }
        i += 1;
    }
    Ok(cp)
}
#[derive(Clone, Debug)]
struct Bootstrap {
    method: u16,
    arguments: Vec<u16>,
}
fn bootstrap_methods(data: &[u8]) -> Result<Vec<Bootstrap>> {
    let mut r = Reader { data, pos: 0 };
    if r.u4()? != 0xCAFEBABE {
        return Err("no es class".into());
    }
    r.u2()?;
    r.u2()?;
    let cp = read_cp(&mut r)?;
    r.take(6)?;
    let n = r.u2()? as usize;
    r.take(n * 2)?;
    for _ in 0..r.u2()? {
        r.take(6)?;
        skip_attrs(&mut r)?;
    }
    for _ in 0..r.u2()? {
        r.take(6)?;
        skip_attrs(&mut r)?;
    }
    let mut result = None;
    for _ in 0..r.u2()? {
        let name = r.u2()?;
        let len = r.u4()? as usize;
        let bytes = r.take(len)?;
        if utf(&cp, name)? != "BootstrapMethods" {
            continue;
        }
        if result.is_some() {
            return Err("BootstrapMethods duplicado".into());
        }
        let mut x = Reader {
            data: bytes,
            pos: 0,
        };
        let count = x.u2()? as usize;
        let mut items = Vec::with_capacity(count);
        for _ in 0..count {
            let method = x.u2()?;
            let n = x.u2()? as usize;
            let mut arguments = Vec::with_capacity(n);
            for _ in 0..n {
                arguments.push(x.u2()?);
            }
            items.push(Bootstrap { method, arguments });
        }
        if x.pos != bytes.len() {
            return Err("BootstrapMethods con bytes sobrantes".into());
        }
        result = Some(items);
    }
    result.ok_or_else(|| "BootstrapMethods ausente".into())
}
fn find_method(data: &[u8], wanted: &str, desc: &str) -> Result<Method> {
    find_method_with_handlers(data, wanted, desc, false)
}
fn find_method_with_handlers(
    data: &[u8],
    wanted: &str,
    desc: &str,
    allow_handlers: bool,
) -> Result<Method> {
    find_method_inner(data, wanted, desc, allow_handlers, true, false)
}
fn find_instance_method(data: &[u8], wanted: &str, desc: &str) -> Result<Method> {
    find_method_inner(data, wanted, desc, false, false, false)
}
fn find_method_inner(
    data: &[u8],
    wanted: &str,
    desc: &str,
    allow_handlers: bool,
    require_static: bool,
    allow_synchronized: bool,
) -> Result<Method> {
    let mut r = Reader { data, pos: 0 };
    if r.u4()? != 0xCAFEBABE {
        return Err("no es un archivo .class".into());
    }
    r.u2()?;
    r.u2()?;
    let cp = read_cp(&mut r)?;
    r.take(6)?;
    let interfaces = r.u2()? as usize;
    r.take(interfaces * 2)?;
    let fields = r.u2()?;
    for _ in 0..fields {
        r.take(6)?;
        skip_attrs(&mut r)?;
    }
    let methods = r.u2()?;
    for _ in 0..methods {
        let flags = r.u2()?;
        let ni = r.u2()?;
        let di = r.u2()?;
        let matches = utf(&cp, ni)? == wanted && utf(&cp, di)? == desc;
        let attrs = r.u2()?;
        for _ in 0..attrs {
            let name = r.u2()?;
            let len = r.u4()? as usize;
            let data = r.take(len)?;
            if matches && utf(&cp, name)? == "Code" {
                if (flags & 0x0008 != 0) != require_static {
                    return Err(if require_static {
                        "el método no es static"
                    } else {
                        "el método no es de instancia"
                    }
                    .into());
                }
                if flags & 0x0020 != 0 && !allow_synchronized {
                    return Err("métodos synchronized todavía no soportados".into());
                }
                let mut cr = Reader { data, pos: 0 };
                cr.u2()?;
                let locals = cr.u2()? as usize;
                let length = cr.u4()? as usize;
                let code = cr.take(length)?.to_vec();
                let summary =
                    bytecode::scan(&code).map_err(|e| format!("bytecode inválido: {e}"))?;
                let count = cr.u2()? as usize;
                if count != 0 && !allow_handlers {
                    return Err("tablas de excepciones todavía no soportadas".into());
                }
                let mut handlers = Vec::with_capacity(count);
                for _ in 0..count {
                    let start = cr.u2()? as usize;
                    let end = cr.u2()? as usize;
                    let target = cr.u2()? as usize;
                    let catch = cr.u2()?;
                    if start >= end
                        || end > code.len()
                        || !summary.boundaries.contains(&start)
                        || (end != code.len() && !summary.boundaries.contains(&end))
                        || !summary.boundaries.contains(&target)
                    {
                        return Err("tabla de excepciones con rango o destino inválido".into());
                    }
                    let catch_type = if catch == 0 {
                        None
                    } else {
                        match cp.get(catch as usize) {
                            Some(CpEntry::Class(n)) => Some(utf(&cp, *n)?.to_owned()),
                            _ => return Err("tipo de excepción Class inválido".into()),
                        }
                    };
                    handlers.push(ExceptionHandler {
                        start,
                        end,
                        target,
                        catch_type,
                    });
                }
                skip_attrs(&mut cr)?;
                return Ok(Method {
                    code,
                    locals,
                    cp,
                    handlers,
                    synchronized: flags & 0x0020 != 0,
                });
            }
        }
    }
    Err(format!(
        "no se encontró el método static {wanted}{desc} con Code"
    ))
}
fn arg_count(desc: &str) -> Result<usize> {
    let (args, ret) = desc
        .strip_prefix('(')
        .and_then(|s| s.split_once(')'))
        .ok_or("descriptor inválido")?;
    if !args
        .bytes()
        .all(|b| matches!(b, b'I' | b'Z' | b'B' | b'C' | b'S'))
        || !matches!(ret, "I" | "Z" | "B" | "C" | "S")
    {
        return Err("solo se admiten argumentos y retornos int/boolean/byte/char/short".into());
    }
    Ok(args.len())
}
fn return_expr(value: &str, return_type: char) -> String {
    match return_type {
        'Z' => format!("({value}) & 1"),
        'B' => format!("(({value}) as i8) as i32"),
        'C' => format!("(({value}) as u16) as i32"),
        'S' => format!("(({value}) as i16) as i32"),
        _ => value.to_owned(),
    }
}
fn pop(stack: &mut Vec<String>, pc: usize) -> Result<String> {
    stack
        .pop()
        .ok_or_else(|| format!("pila vacía en bytecode offset {pc}"))
}
struct Compiler<'a> {
    class_data: &'a [u8],
    class_name: &'a str,
    jar: Option<&'a Path>,
    active: Vec<String>,
    functions: Vec<String>,
    serial: usize,
}
impl Compiler<'_> {
    fn compile(&mut self, name: &str, desc: &str) -> Result<String> {
        self.compile_for(self.class_name, name, desc)
    }
    fn compile_for(&mut self, current_class: &str, name: &str, desc: &str) -> Result<String> {
        let key = format!("{current_class}.{name}{desc}");
        if self.active.contains(&key) {
            return Err(format!("recursión no soportada: {key}"));
        }
        if self.active.len() >= 32 {
            return Err("profundidad de llamadas mayor a 32".into());
        }
        let count = arg_count(desc)?;
        let return_type = desc.chars().last().ok_or("descriptor vacío")?;
        let other = if current_class != self.class_name {
            let jar = self.jar.ok_or("sin JAR para resolver clase externa")?;
            Some(class_from_jar(jar, current_class)?)
        } else {
            None
        };
        let data = other.as_deref().unwrap_or(self.class_data);
        let m = find_method(data, name, desc)?;
        let rust_name = format!("translated_{}", self.serial);
        self.serial += 1;
        self.active.push(key);
        let checkpoint = self.functions.len();
        let body = match translate(&m, count, &rust_name, current_class, return_type, self) {
            Ok(body) => Ok(body),
            Err(linear_err) => {
                self.functions.truncate(checkpoint);
                flow::translate_flow(&m, count, &rust_name, current_class, return_type, self)
                    .map_err(|flow_err| {
                        format!("traducción lineal: {linear_err}; control de flujo: {flow_err}")
                    })
            }
        };
        self.active.pop();
        self.functions.push(body?);
        Ok(rust_name)
    }
}
fn translate(
    m: &Method,
    count: usize,
    rust_name: &str,
    current_class: &str,
    return_type: char,
    ctx: &mut Compiler<'_>,
) -> Result<String> {
    if count > m.locals {
        return Err("max_locals menor que el número de argumentos".into());
    }
    let mut locals: Vec<Option<String>> = (0..m.locals)
        .map(|i| {
            if i < count {
                Some(format!("a{i}"))
            } else {
                None
            }
        })
        .collect();
    let mut stack = Vec::<String>::new();
    let mut lines = String::new();
    let mut pc = 0;
    let mut tmp = 0;
    while pc < m.code.len() {
        let start = pc;
        let op = m.code[pc];
        pc += 1;
        let load = match op {
            0x1a..=0x1d => Some((op - 0x1a) as usize),
            0x15 => {
                let b = *m.code.get(pc).ok_or("iload truncado")?;
                pc += 1;
                Some(b as usize)
            }
            _ => None,
        };
        if let Some(idx) = load {
            let value = locals
                .get(idx)
                .and_then(|v| v.as_ref())
                .ok_or_else(|| format!("local {idx} sin inicializar en {start}"))?;
            stack.push(value.clone());
            continue;
        }
        match op {
            0x00 => {}
            0x57 => {
                pop(&mut stack, start)?;
            }
            0x59 => {
                let v = stack
                    .last()
                    .ok_or_else(|| format!("pila vacía en {start}"))?
                    .clone();
                stack.push(v);
            }
            0x5f => {
                if stack.len() < 2 {
                    return Err(format!("pila vacía en {start}"));
                }
                let len = stack.len();
                stack.swap(len - 1, len - 2);
            }
            0x6c | 0x70 => {
                let b = pop(&mut stack, start)?;
                let a = pop(&mut stack, start)?;
                let f = if op == 0x6c {
                    "java_int_div"
                } else {
                    "java_int_rem"
                };
                lines.push_str(&format!("    let t{tmp}: i32 = {f}({a}, {b});\n"));
                stack.push(format!("t{tmp}"));
                tmp += 1;
            }
            0x91..=0x93 => {
                let a = pop(&mut stack, start)?;
                let ty = match op {
                    0x91 => "i8",
                    0x92 => "u16",
                    _ => "i16",
                };
                lines.push_str(&format!("    let t{tmp}: i32 = ({a} as {ty}) as i32;\n"));
                stack.push(format!("t{tmp}"));
                tmp += 1;
            }
            0x02..=0x08 => stack.push(format!("{}i32", op as i8 - 3)),
            0x10 => {
                let v = *m.code.get(pc).ok_or("bipush truncado")? as i8;
                pc += 1;
                stack.push(format!("{v}i32"));
            }
            0x11 => {
                let a = *m.code.get(pc).ok_or("sipush truncado")?;
                let b = *m.code.get(pc + 1).ok_or("sipush truncado")?;
                pc += 2;
                stack.push(format!("{}i32", i16::from_be_bytes([a, b])));
            }
            0x12 | 0x13 => {
                let index = if op == 0x12 {
                    let i = *m.code.get(pc).ok_or("ldc truncado")? as u16;
                    pc += 1;
                    i
                } else {
                    let a = *m.code.get(pc).ok_or("ldc_w truncado")?;
                    let b = *m.code.get(pc + 1).ok_or("ldc_w truncado")?;
                    pc += 2;
                    u16::from_be_bytes([a, b])
                };
                match m.cp.get(index as usize) {
                    Some(CpEntry::Integer(v)) => stack.push(format!("{v}i32")),
                    _ => {
                        return Err(format!(
                            "ldc solo admite constantes int; índice {index} en offset {start}"
                        ))
                    }
                }
            }
            0xb8 => {
                let a = *m.code.get(pc).ok_or("invokestatic truncado")?;
                let b = *m.code.get(pc + 1).ok_or("invokestatic truncado")?;
                pc += 2;
                let (class, name, desc) = method_ref(&m.cp, u16::from_be_bytes([a, b]))?;
                let expr = match (class, name, desc) {
                    ("java/lang/Math", "abs", "(I)I") => {
                        let x = pop(&mut stack, start)?;
                        format!("({x}).wrapping_abs()")
                    }
                    ("java/lang/Math", "min", "(II)I") | ("java/lang/Math", "max", "(II)I") => {
                        let y = pop(&mut stack, start)?;
                        let x = pop(&mut stack, start)?;
                        format!("std::cmp::{name}({x}, {y})")
                    }
                    ("java/lang/Math", "floorDiv" | "floorMod", "(II)I") => {
                        let y = pop(&mut stack, start)?;
                        let x = pop(&mut stack, start)?;
                        let f = if name == "floorDiv" {
                            "java_floor_div"
                        } else {
                            "java_floor_mod"
                        };
                        format!("{f}({x}, {y})")
                    }
                    _ if class == current_class || class.starts_with("net/minecraft/") => {
                        let n = arg_count(desc)?;
                        let mut args = Vec::with_capacity(n);
                        for _ in 0..n {
                            args.push(pop(&mut stack, start)?);
                        }
                        args.reverse();
                        let target = ctx.compile_for(class, name, desc)?;
                        format!("{target}({})", args.join(", "))
                    }
                    _ => {
                        return Err(format!(
                            "invokestatic no soportado: {class}.{name}{desc} en offset {start}"
                        ))
                    }
                };
                lines.push_str(&format!("    let t{tmp}: i32 = {expr};\n"));
                stack.push(format!("t{tmp}"));
                tmp += 1;
            }
            0x36 | 0x3b..=0x3e => {
                let idx = if op == 0x36 {
                    let i = *m.code.get(pc).ok_or("istore truncado")? as usize;
                    pc += 1;
                    i
                } else {
                    (op - 0x3b) as usize
                };
                if idx >= locals.len() {
                    return Err(format!("local fuera de rango: {idx}"));
                }
                let v = pop(&mut stack, start)?;
                // Snapshot values so later writes to the local do not alter stack entries.
                lines.push_str(&format!("    let t{tmp}: i32 = {v};\n"));
                locals[idx] = Some(format!("t{tmp}"));
                tmp += 1;
            }
            0x60 | 0x64 | 0x68 | 0x78 | 0x7a | 0x7c | 0x7e | 0x80 | 0x82 => {
                let b = pop(&mut stack, start)?;
                let a = pop(&mut stack, start)?;
                let expr = match op {
                    0x60 => format!("({a}).wrapping_add({b})"),
                    0x64 => format!("({a}).wrapping_sub({b})"),
                    0x68 => format!("({a}).wrapping_mul({b})"),
                    0x78 => format!("({a}).wrapping_shl(({b} as u32) & 31)"),
                    0x7a => format!("({a}).wrapping_shr(({b} as u32) & 31)"),
                    0x7c => format!("(({a} as u32) >> (({b} as u32) & 31)) as i32"),
                    0x7e => format!("({a}) & ({b})"),
                    0x80 => format!("({a}) | ({b})"),
                    _ => format!("({a}) ^ ({b})"),
                };
                lines.push_str(&format!("    let t{tmp}: i32 = {expr};\n"));
                stack.push(format!("t{tmp}"));
                tmp += 1;
            }
            0x74 => {
                let a = pop(&mut stack, start)?;
                lines.push_str(&format!("    let t{tmp}: i32 = ({a}).wrapping_neg();\n"));
                stack.push(format!("t{tmp}"));
                tmp += 1;
            }
            0xac => {
                let value = pop(&mut stack, start)?;
                if !stack.is_empty() || pc != m.code.len() {
                    return Err("ireturn con pila extra o bytecode restante: no soportado".into());
                }
                let value = return_expr(&value, return_type);
                lines.push_str(&format!("    {value}\n"));
                let params = (0..count)
                    .map(|i| format!("a{i}: i32"))
                    .collect::<Vec<_>>()
                    .join(", ");
                return Ok(format!("fn {rust_name}({params}) -> i32 {{\n{lines}}}\n"));
            }
            _ => {
                return Err(format!(
                    "opcode no soportado 0x{op:02x} en offset {start}; no se produjo binario"
                ))
            }
        }
    }
    Err("el método no termina con ireturn".into())
}
fn extract(jar: &Path, member: &str) -> Result<Vec<u8>> {
    let out = Command::new("unzip")
        .arg("-p")
        .arg(jar)
        .arg(member)
        .output()
        .map_err(|e| format!("no se pudo ejecutar unzip: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "no se pudo extraer {member}: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    Ok(out.stdout)
}
fn run() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    if matches!(
        args.get(1).map(String::as_str),
        Some("concurrent-int-demo" | "concurrent-rayon-int-demo")
    ) {
        if args.len() != 7 {
            return Err(
                "uso: mc-aot concurrent-int-demo <jar> <clase> <binario> <método> '(I)I'".into(),
            );
        }
        let rayon = args[1] == "concurrent-rayon-int-demo";
        let source =
            concurrent_compile::compile(Path::new(&args[2]), &args[3], &args[5], &args[6], rayon)?;
        return if rayon {
            emit_rayon_binary(&args[4], &source)
        } else {
            emit_binary(&args[4], &source)
        };
    }
    if args.get(1).map(String::as_str)==Some("shared-worker-demo") {
        let wrapper=match args.get(9).map(String::as_str) {None if args.len()==9=>shared_worker::WorkerWrapper::None,Some("--util-named-wrapper") if args.len()==10=>shared_worker::WorkerWrapper::Util4,Some("--ticktask-wrapper") if args.len()==10=>shared_worker::WorkerWrapper::TickTask,_=>return Err("uso: mc-aot shared-worker-demo <jar> <clase-raíz> <campo-static> <clase-runnable> <binario> <tick> <lectura> [--util-named-wrapper|--ticktask-wrapper]".into())};
        let jar=Path::new(&args[2]);let plan=shared_worker::verify(jar,&args[3],&args[4],&args[5],&args[7],&args[8],wrapper)?;
        let methods=vec![(args[7].clone(),"(I)I".to_owned()),(args[8].clone(),"(I)I".to_owned())];
        let source=numeric::compile_shared_worker_demo(jar,&args[3],&methods,&plan)?;
        return emit_rayon_binary(&args[6],&source);
    }
    if args.get(1).map(String::as_str) == Some("split-source") {
        if args.len() != 4 {
            return Err("uso: mc-aot split-source <source.rs> <outdir>".into());
        }
        let source = fs::read_to_string(Path::new(&args[2])).map_err(|e| format!("no se pudo leer {}: {e}", args[2]))?;
        let files = split_source::split_crate(&source).map_err(|e| format!("split falló: {e}"))?;
        let outdir = PathBuf::from(&args[3]);
        if outdir.exists() {
            fs::remove_dir_all(&outdir).map_err(|e| format!("no se pudo limpiar {}: {e}", outdir.display()))?;
        }
        for (rel, contents) in &files {
            let path = outdir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent).map_err(|e| format!("mkdir {}: {e}", parent.display()))?;
            }
            fs::write(&path, contents).map_err(|e| format!("write {}: {e}", path.display()))?;
        }
        println!("workspace en {}", outdir.display());
        return Ok(());
    }
    if args.get(1).map(String::as_str) == Some("multi-static-demo") {
        if args.len() < 7 || (args.len() - 5) % 2 != 0 {
            return Err("uso: mc-aot multi-static-demo <server.jar> <clase> <binario> <método> <descriptor> [...]".into());
        }
        let methods = args[5..]
            .chunks_exact(2)
            .map(|x| (x[0].clone(), x[1].clone()))
            .collect::<Vec<_>>();
        let source = numeric::compile_multi_static_demo(Path::new(&args[2]), &args[3], &methods)?;
        return emit_binary_split(&args[4], &source);
    }
    if args.get(1).map(String::as_str) == Some("static-demo") {
        if args.len() < 7 || (args.len() - 5) % 2 != 0 {
            return Err("uso: mc-aot static-demo <server.jar> <clase> <binario> <método> <descriptor> [<método> <descriptor> ...]".into());
        }
        let methods = args[5..]
            .chunks_exact(2)
            .map(|x| (x[0].clone(), x[1].clone()))
            .collect::<Vec<_>>();
        let source = numeric::compile_static_demo(Path::new(&args[2]), &args[3], &methods)?;
        return emit_binary(&args[4], &source);
    }
    if args.len() == 3 && args[1] == "graph-dir" {
        return metadata::graph_dir(Path::new(&args[2]));
    }
    if args.len() == 3 && args[1] == "index-dir" {
        return metadata::index_dir(Path::new(&args[2]));
    }
    if args.len() == 4 && args[1] == "inspect" {
        let class = class_from_jar(Path::new(&args[2]), &args[3])?;
        return metadata::inspect(&class);
    }
    if args.get(1).map(String::as_str) == Some("object-demo")
        && (args.len() == 5 || (args.len() == 8 && args[5] == "--default"))
    {
        let class = class_from_jar(Path::new(&args[2]), &args[3])?;
        let interface = if args.len() == 8 {
            Some(class_from_jar(Path::new(&args[2]), &args[6])?)
        } else {
            None
        };
        let selected = interface
            .as_deref()
            .map(|data| (data, args[6].as_str(), args[7].as_str()));
        let program = object::compile_object(&class, &args[3], selected)?;
        return emit_binary(&args[4], &program.source);
    }
    if args.len() == 5 && args[1] == "class-demo" {
        // A-02 fase 3: una clase vanilla completa, todas sus declaraciones.
        let source = numeric::compile_class_demo(Path::new(&args[2]), &args[3])?;
        return emit_binary(&args[4], &source);
    }
    if args.len() == 6 && args[1] == "reference-demo" {
        let class = class_from_jar(Path::new(&args[2]), &args[3])?;
        let source = reference::compile_reference(&class, &args[3], &args[4])?;
        return emit_binary(&args[5], &source);
    }
    if (args.len() == 8 || (args.len() == 11 && args[8] == "--reference"))
        && args[1] == "multi-demo"
    {
        let jar = Path::new(&args[2]);
        let class0 = class_from_jar(jar, &args[3])?;
        let class1 = class_from_jar(jar, &args[4])?;
        let interface = class_from_jar(jar, &args[5])?;
        let a = object::compile_object(&class0, &args[3], Some((&interface, &args[5], &args[6])))?;
        let b = object::compile_object(&class1, &args[4], Some((&interface, &args[5], &args[6])))?;
        let ref_source = if args.len() == 11 {
            let data = class_from_jar(jar, &args[9])?;
            Some(reference::compile_reference(&data, &args[9], &args[10])?)
        } else {
            None
        };
        let source = multi::compile_multi(&a, &b, ref_source.as_deref())?;
        return emit_binary(&args[7], &source);
    }
    let usage = "uso: mc-aot compile <server.jar> <clase/sin/.class> <método> <descriptor> <binario>\n     mc-aot compile-numeric <server.jar> <clase> <método> <descriptor> <binario>\n     mc-aot multi-static-demo <server.jar> <clase> <binario> <método> <descriptor> [<método> <descriptor> ...]\n     mc-aot shared-worker-demo <server.jar> <clase-raíz> <campo-static> <clase-runnable> <binario> <tick> <lectura> [--util-named-wrapper|--ticktask-wrapper]\n     mc-aot concurrent-int-demo <server.jar> <clase> <binario> <método> '(I)I'\n     mc-aot concurrent-rayon-int-demo <server.jar> <clase> <binario> <método> '(I)I'\n     mc-aot static-demo <server.jar> <clase> <binario> <método> <descriptor> [<método> <descriptor> ...]\n     mc-aot object-demo <server.jar> <clase> <binario> [--default <interfaz> <método>]\n     mc-aot multi-demo <server.jar> <clase1> <clase2> <interfaz> <default> <binario> [--reference <clase> <getter>]\n     mc-aot reference-demo <server.jar> <clase> <getter> <binario>\n     mc-aot inspect <server.jar> <clase>\n     mc-aot index-dir <directorio-de-class>\n     mc-aot graph-dir <directorio-de-class>\nArrays CLI (I/J/Z/B/C/S): null, [], [1,2] o @0 para reutilizar un array anterior.\nString: null o s:contenido; String[]: null o sarr:[x<hex-UTF8>,n,...], n=null y x=cadena vacía.\nHeap experimental: 10 000 objetos/arrays, 1 000 000 elementos y unidades UTF-16 acumulados; sin GC.\nEl análisis es estructural, no verifica la semántica ni traduce clases. Solo archivos de confianza.\nejemplo: mc-aot compile server.jar net/minecraft/util/Mth square '(I)I' ./square";
    if args.len() == 2 && matches!(args[1].as_str(), "--help" | "-h") {
        println!("{usage}");
        return Ok(());
    }
    if args.len() != 7 || !matches!(args[1].as_str(), "compile" | "compile-numeric") {
        return Err(usage.into());
    }
    if args[1] == "compile-numeric"
        || args[5].contains('J')
        || args[5].contains('[')
        || args[5].ends_with(")V")
        || args[5].contains("Ljava/lang/String;")
    {
        let source = numeric::compile_jar(Path::new(&args[2]), &args[3], &args[4], &args[5])?;
        return emit_binary(&args[6], &source);
    }
    let count = arg_count(&args[5])?;
    let class = class_from_jar(Path::new(&args[2]), &args[3])?;
    let mut compiler = Compiler {
        class_data: &class,
        class_name: &args[3],
        jar: Some(Path::new(&args[2])),
        active: Vec::new(),
        functions: Vec::new(),
        serial: 0,
    };
    let entry = match compiler.compile(&args[4], &args[5]) {
        Ok(entry) => entry,
        Err(original) => {
            let source = numeric::compile_jar(Path::new(&args[2]), &args[3], &args[4], &args[5])
                .map_err(|e| format!("traductor entero: {original}; traductor numérico: {e}"))?;
            return emit_binary(&args[6], &source);
        }
    };
    let translated = compiler.functions.join("\n");
    let arg_types = args[5]
        .strip_prefix('(')
        .unwrap()
        .split_once(')')
        .unwrap()
        .0
        .as_bytes();
    let reads = arg_types.iter().enumerate().map(|(i, ty)| {
        let valid = match ty {
            b'Z' => "(0..=1)",
            b'B' => "(-128..=127)",
            b'C' => "(0..=65535)",
            b'S' => "(-32768..=32767)",
            _ => "(i32::MIN..=i32::MAX)",
        };
        format!("    let a{i}: i32 = args[{i}].parse().unwrap_or_else(|_| {{ eprintln!(\"argumento {i} no es un entero de 32 bits\"); std::process::exit(2) }});\n    if !{valid}.contains(&a{i}) {{ eprintln!(\"argumento {i} fuera del rango Java para {}\"); std::process::exit(2); }}\n", *ty as char)
    }).collect::<String>();
    let call = (0..count)
        .map(|i| format!("a{i}"))
        .collect::<Vec<_>>()
        .join(", ");
    let runtime = r#"
#[allow(dead_code)]
fn java_int_div(a: i32, b: i32) -> i32 {
    if b == 0 { eprintln!("ArithmeticException: / by zero"); std::process::exit(2); }
    a.wrapping_div(b)
}
#[allow(dead_code)]
fn java_int_rem(a: i32, b: i32) -> i32 {
    if b == 0 { eprintln!("ArithmeticException: / by zero"); std::process::exit(2); }
    a.wrapping_rem(b)
}
#[allow(dead_code)]
fn java_floor_div(a: i32, b: i32) -> i32 {
    if b == 0 { eprintln!("ArithmeticException: / by zero"); std::process::exit(2); }
    let q = a.wrapping_div(b); let r = a.wrapping_rem(b);
    if r != 0 && (a ^ b) < 0 { q.wrapping_sub(1) } else { q }
}
#[allow(dead_code)]
fn java_floor_mod(a: i32, b: i32) -> i32 {
    if b == 0 { eprintln!("ArithmeticException: / by zero"); std::process::exit(2); }
    let r = a.wrapping_rem(b);
    if r != 0 && (a ^ b) < 0 { r.wrapping_add(b) } else { r }
}
"#;
    let translated = format!("{runtime}\n{translated}");
    let source = format!("// Generado por mc-aot: {}.{}{}\n{}\nfn main() {{\n    let args: Vec<String> = std::env::args().skip(1).collect();\n    if args.len() != {count} {{ eprintln!(\"Se esperaban {count} argumentos numéricos\"); std::process::exit(2); }}\n{reads}    println!(\"{{}}\", {entry}({call}));\n}}\n", args[3], args[4], args[5], translated);
    emit_binary(&args[6], &source)
}
// La dependencia se compila en un proyecto temporal con lockfile versionado;
// el binario resultante no carga Rayon dinámicamente en ejecución.
fn emit_rayon_binary(output_path: &str, source: &str) -> Result<()> {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let name = format!("mc-aot-generated-{}-{nonce}", std::process::id());
    let dir = std::env::temp_dir().join(&name);
    fs::create_dir(&dir).map_err(|e| format!("no se pudo crear proyecto temporal: {e}"))?;
    struct Clean(PathBuf);
    impl Drop for Clean {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    let _clean = Clean(dir.clone());
    let output = PathBuf::from(output_path);
    let source_path = PathBuf::from(format!("{}.rs", output.display()));
    fs::write(&source_path, source).map_err(|e| format!("no se pudo escribir fuente: {e}"))?;
    let manifest=format!("[package]\nname=\"mc-aot\"\nversion=\"0.1.0\"\nedition=\"2021\"\n[[bin]]\nname=\"{name}\"\npath=\"main.rs\"\n[dependencies]\nrayon=\"=1.11.0\"\n[profile.release]\npanic=\"unwind\"\nstrip=\"symbols\"\n");
    fs::write(dir.join("Cargo.toml"), manifest).map_err(|e| e.to_string())?;
    fs::write(dir.join("Cargo.lock"), include_str!("../Cargo.lock")).map_err(|e| e.to_string())?;
    fs::write(dir.join("main.rs"), source).map_err(|e| e.to_string())?;
    let target = std::env::var_os("MC_AOT_RAYON_TARGET_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::temp_dir().join("mc-aot-rayon-target"));
    let status = Command::new("cargo")
        .arg("build")
        .arg("--release")
        .arg("--locked")
        .arg("--quiet")
        .arg("--manifest-path")
        .arg(dir.join("Cargo.toml"))
        .env("CARGO_TARGET_DIR", &target)
        .status()
        .map_err(|e| format!("no se pudo iniciar cargo: {e}"))?;
    if !status.success() {
        return Err("cargo falló; no se puede asegurar un binario válido".into());
    }
    fs::copy(target.join("release").join(&name), &output)
        .map_err(|e| format!("no se pudo copiar binario: {e}"))?;
    println!(
        "Binario nativo con Rayon: {}\nRust generado: {}",
        output.display(),
        source_path.display()
    );
    Ok(())
}
fn emit_binary_split(output_path: &str, source: &str) -> Result<()> {
    let out = PathBuf::from(output_path);
    let split_dir = PathBuf::from(format!("{}.split", out.display()));
    if split_dir.exists() {
        fs::remove_dir_all(&split_dir).map_err(|e| format!("no se pudo limpiar {}: {e}", split_dir.display()))?;
    }
    let files = split_source::split_crate(source).map_err(|e| format!("split del fuente falló: {e}"))?;
    for (rel, contents) in &files {
        let path = split_dir.join(rel.replace('/', std::path::MAIN_SEPARATOR_STR));
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("mkdir {}: {e}", parent.display()))?;
        }
        fs::write(&path, contents).map_err(|e| format!("write {}: {e}", path.display()))?;
    }
    // Escribir una copia del fuente íntegro para inspección/depuración
    let source_path = PathBuf::from(format!("{}.rs", out.display()));
    fs::write(&source_path, source).map_err(|e| format!("no se pudo escribir fuente: {e}"))?;
    let release = std::env::var_os("MC_AOT_SPLIT_RELEASE").is_some();
    let mut cmd = Command::new("cargo");
    cmd.arg("build").arg("--quiet");
    if release {
        cmd.arg("--release");
    }
    cmd.arg("--manifest-path")
        .arg(split_dir.join("Cargo.toml"))
        .env("CARGO_BUILD_JOBS", "1");
    let status = cmd.status().map_err(|e| format!("no se pudo iniciar cargo: {e}"))?;
    if !status.success() {
        return Err("cargo falló; no se puede asegurar un binario válido".into());
    }
    let profile = if release { "release" } else { "debug" };
    let built = split_dir.join("target").join(profile).join("mc_aot_generated");
    fs::copy(&built, &out).map_err(|e| format!("no se pudo copiar binario {}: {e}", built.display()))?;
    println!(
        "Binario nativo (split): {}\nWorkspace: {}\nRust generado: {}",
        out.display(),
        split_dir.display(),
        source_path.display()
    );
    Ok(())
}

fn emit_binary(output_path: &str, source: &str) -> Result<()> {
    let output = PathBuf::from(output_path);
    let source_path = PathBuf::from(format!("{}.rs", output.display()));
    fs::write(&source_path, source).map_err(|e| format!("no se pudo escribir fuente: {e}"))?;
    let status = Command::new("rustc")
        .arg("--edition=2021")
        .arg("-O")
        .arg("-C")
        .arg("panic=unwind")
        .arg("-C")
        .arg("strip=symbols")
        .arg("--crate-name")
        .arg("mc_aot_generated")
        .arg(&source_path)
        .arg("-o")
        .arg(&output)
        .status()
        .map_err(|e| format!("no se pudo iniciar rustc: {e}"))?;
    if !status.success() {
        return Err("rustc falló; no se puede asegurar un binario válido".into());
    }
    println!(
        "Binario nativo: {}\nRust generado: {}",
        output.display(),
        source_path.display()
    );
    Ok(())
}
fn main() {
    let result = run();
    classpath::clear();
    if let Err(e) = result {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn translate_test(m: &Method, count: usize) -> Result<String> {
        let mut ctx = Compiler {
            class_data: &[],
            class_name: "",
            jar: None,
            active: vec![],
            functions: vec![],
            serial: 0,
        };
        translate(m, count, "translated", "", 'I', &mut ctx)
    }
    // Prueba de integración de prototipos, no del backend principal generado.
    #[test]
    fn rayon_shared_identity_and_concurrent_initialization() {
        use crate::class_init::ClassInit;
        use crate::concurrent_heap::{SharedHeap, Value};
        use crate::rayon_scheduler::WorkerPool;
        use std::sync::{Arc, Barrier};
        use std::sync::atomic::{AtomicUsize, Ordering};
        fn worker(heap: SharedHeap, statics: crate::concurrent_heap::ObjectId, init: Arc<ClassInit>, calls: Arc<AtomicUsize>, gate: Arc<Barrier>) {
            gate.wait();
            init.ensure(|| {
                calls.fetch_add(1,Ordering::SeqCst);
                let object=heap.allocate_typed("test/Cell",vec![Value::Int(0),Value::Ref(None)]).map_err(|_|())?;
                heap.write(object,1,Value::Ref(Some(object))).map_err(|_|())?;
                heap.write(statics,0,Value::Ref(Some(object))).map_err(|_|())?;
                Ok(())
            }).unwrap();
            let Value::Ref(Some(object))=heap.read(statics,0).unwrap() else {panic!("inicialización no publicada")};
            assert_eq!(heap.read(object,1).unwrap(),Value::Ref(Some(object)));
            for _ in 0..100 {
                let _guard=heap.enter(object).unwrap();
                let _reentrant=heap.enter(object).unwrap();
                let Value::Int(v)=heap.read(object,0).unwrap() else {panic!("campo inesperado")};
                heap.write(object,0,Value::Int(v+1)).unwrap();
            }
        }
        for _ in 0..20 {
            let heap=SharedHeap::default();let statics=heap.allocate(vec![Value::Ref(None)]).unwrap();
            let init=Arc::new(ClassInit::default());let calls=Arc::new(AtomicUsize::new(0));let gate=Arc::new(Barrier::new(5));
            let pool=WorkerPool::new(4).unwrap();let mut jobs=Vec::new();
            for _ in 0..4 {let (h,i,c,g)=(heap.clone(),init.clone(),calls.clone(),gate.clone());jobs.push(pool.submit(move||worker(h,statics,i,c,g)).unwrap());}
            worker(heap.clone(),statics,init.clone(),calls.clone(),gate.clone());
            for job in jobs {job.get().unwrap();}
            assert_eq!(calls.load(Ordering::SeqCst),1);
            let Value::Ref(Some(object))=heap.read(statics,0).unwrap() else {panic!("sin objeto")};
            assert_eq!(heap.read(object,0).unwrap(),Value::Int(500));
            assert_eq!(heap.read(object,1).unwrap(),Value::Ref(Some(object)));
            let foreign=SharedHeap::default();
            assert!(foreign.read(object,0).is_err());
            assert_eq!(pool.shutdown().unwrap(),0);
        }
    }

    #[test]
    fn descriptor_restrictions() {
        assert_eq!(arg_count("(III)I").unwrap(), 3);
        assert!(arg_count("(J)I").is_err());
        assert_eq!(arg_count("(IZBCS)I").unwrap(), 5);
        assert!(arg_count("(I)V").is_err());
        assert_eq!(arg_count("(II)Z").unwrap(), 2);
        assert_eq!(return_expr("a", 'Z'), "(a) & 1");
        assert_eq!(return_expr("a", 'B'), "((a) as i8) as i32");
    }
    #[test]
    fn square_is_translated() {
        let m = Method {
            code: vec![0x1a, 0x1a, 0x68, 0xac],
            locals: 1,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        let code = translate_test(&m, 1).unwrap();
        assert!(code.contains("wrapping_mul"));
    }
    #[test]
    fn unsupported_opcode_fails() {
        let m = Method {
            code: vec![0xff, 0xac],
            locals: 0,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        assert!(translate_test(&m, 0).unwrap_err().contains("0xff"));
    }
    #[test]
    fn int_ldc_translates() {
        let m = Method {
            code: vec![0x12, 1, 0xac],
            locals: 0,
            cp: vec![CpEntry::Empty, CpEntry::Integer(-99)],
            handlers: vec![],
            synchronized: false,
        };
        assert!(translate_test(&m, 0).unwrap().contains("-99i32"));
    }
    #[test]
    fn bad_invokestatic_is_rejected() {
        let m = Method {
            code: vec![0xb8, 0, 1, 0xac],
            locals: 0,
            cp: vec![CpEntry::Empty],
            handlers: vec![],
            synchronized: false,
        };
        assert!(translate_test(&m, 0).is_err());
    }
    #[test]
    fn mutf8_handles_java_strings() {
        let x = JavaUtf8::decode(&[b'A', 0xc0, 0x80, 0xed, 0xa0, 0xbd, 0xed, 0xb8, 0x80]).unwrap();
        assert_eq!(x.units, vec![65, 0, 0xd83d, 0xde00]);
        assert_eq!(x.text.as_deref(), Some("A\0😀"));
        let lone = JavaUtf8::decode(&[0xed, 0xa0, 0x80]).unwrap();
        assert_eq!(lone.units, vec![0xd800]);
        assert!(lone.text.is_none());
        for invalid in [
            &[0][..],
            &[0xf0, 0x9f, 0x98, 0x80][..],
            &[0xc1, 0x81][..],
            &[0xc2][..],
            &[0xe0, 0x80, 0x80][..],
        ] {
            assert!(JavaUtf8::decode(invalid).is_err());
        }
    }
    #[test]
    fn reject_truncated_class() {
        assert!(find_method(&[0xca, 0xfe], "x", "()I").is_err());
    }
}
