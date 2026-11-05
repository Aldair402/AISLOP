//! Experimental lowering for tiny, simple objects. This is not a Java heap or verifier.
use super::{method_ref, read_cp, skip_attrs, utf, CpEntry, Reader, Result};
use std::collections::HashSet;

pub(super) fn class_name(cp: &[CpEntry], i: u16) -> Result<&str> {
    match cp.get(i as usize) {
        Some(CpEntry::Class(n)) => utf(cp, *n),
        _ => Err("Class inválida".into()),
    }
}
pub(super) fn field_ref(cp: &[CpEntry], index: u16) -> Result<(&str, &str, &str)> {
    let (ci, nt) = match cp.get(index as usize) {
        Some(CpEntry::FieldRef(c, n)) => (*c, *n),
        _ => return Err("Fieldref inválido".into()),
    };
    let (ni, di) = match cp.get(nt as usize) {
        Some(CpEntry::NameType(n, d)) => (*n, *d),
        _ => return Err("NameAndType inválido".into()),
    };
    Ok((class_name(cp, ci)?, utf(cp, ni)?, utf(cp, di)?))
}
#[derive(Clone)]
enum Value {
    This,
    Int(String),
}
fn pop_int(stack: &mut Vec<Value>) -> Result<String> {
    match stack.pop() {
        Some(Value::Int(v)) => Ok(v),
        _ => Err("se esperaba int en la pila".into()),
    }
}
fn pop_this(stack: &mut Vec<Value>) -> Result<()> {
    match stack.pop() {
        Some(Value::This) => Ok(()),
        _ => Err("solo se admite referencia a this".into()),
    }
}
fn lower(
    code: &[u8],
    cp: &[CpEntry],
    owner: &str,
    fields: &[String],
    ctor: bool,
    n_args: usize,
    calls: Option<(&str, &[(String, usize)])>,
) -> Result<String> {
    super::bytecode::scan(code).map_err(|e| format!("bytecode inválido: {e}"))?;
    let mut r = Reader { data: code, pos: 0 };
    let mut stack: Vec<Value> = Vec::new();
    let mut lines = String::new();
    let mut tmp = 0;
    let mut super_called = false;
    while r.pos < code.len() {
        let start = r.pos;
        let op = r.u1()?;
        match op {
            0x57 => {
                stack.pop().ok_or("pila vacía")?;
            }
            0x59 => {
                let x = stack.last().ok_or("pila vacía")?.clone();
                stack.push(x);
            }
            0x5f => {
                if stack.len() < 2 {
                    return Err("pila vacía".into());
                }
                let len = stack.len();
                stack.swap(len - 1, len - 2);
            }
            0x2a => stack.push(Value::This),
            0x1b..=0x1d | 0x15 => {
                let index = if op == 0x15 {
                    r.u1()? as usize
                } else {
                    (op - 0x1a) as usize
                };
                if index == 0 || index > n_args {
                    return Err(format!(
                        "iload {index} no es argumento int en offset {start}"
                    ));
                }
                stack.push(Value::Int(format!("a{}", index - 1)));
            }
            0x02..=0x08 => stack.push(Value::Int(format!("{}i32", op as i8 - 3))),
            0x10 => {
                let n = r.u1()? as i8;
                stack.push(Value::Int(format!("{n}i32")));
            }
            0x11 => {
                let n = r.u2()? as i16;
                stack.push(Value::Int(format!("{n}i32")));
            }
            0xb4 | 0xb5 => {
                let (cl, name, desc) = field_ref(cp, r.u2()?)?;
                if cl != owner || desc != "I" {
                    return Err(format!("campo externo o no int: {cl}.{name}:{desc}"));
                }
                let i = fields
                    .iter()
                    .position(|v| v == name)
                    .ok_or("campo no declarado")?;
                if op == 0xb4 {
                    pop_this(&mut stack)?;
                    lines.push_str(&format!("        let t{tmp} = self.f{i};\n"));
                    stack.push(Value::Int(format!("t{tmp}")));
                    tmp += 1;
                } else {
                    let value = pop_int(&mut stack)?;
                    pop_this(&mut stack)?;
                    lines.push_str(&format!("        self.f{i} = {value};\n"));
                }
            }
            0xb7 => {
                let (cl, name, desc) = method_ref(cp, r.u2()?)?;
                if !ctor
                    || super_called
                    || (cl, name, desc) != ("java/lang/Object", "<init>", "()V")
                {
                    return Err(format!("invokespecial no soportado: {cl}.{name}{desc}"));
                }
                pop_this(&mut stack)?;
                super_called = true;
            }
            0xb9 => {
                let index = r.u2()?;
                let argc = r.u1()?;
                let zero = r.u1()?;
                if argc != 1 || zero != 0 {
                    return Err("invokeinterface con argumentos no soportado".into());
                }
                if !matches!(
                    cp.get(index as usize),
                    Some(CpEntry::InterfaceMethodRef(_, _))
                ) {
                    return Err("invokeinterface requiere InterfaceMethodref".into());
                }
                let (iface, name, desc) = method_ref(cp, index)?;
                let (expected, targets) = calls.ok_or("invokeinterface no soportado aquí")?;
                if iface != expected || desc != "()I" {
                    return Err(format!(
                        "invokeinterface no soportado: {iface}.{name}{desc}"
                    ));
                }
                let target = targets
                    .iter()
                    .find(|(n, _)| n == name)
                    .map(|(_, i)| *i)
                    .ok_or_else(|| format!("destino de interfaz no resuelto: {name}"))?;
                pop_this(&mut stack)?;
                lines.push_str(&format!("        let t{tmp} = self.method_{target}();\n"));
                stack.push(Value::Int(format!("t{tmp}")));
                tmp += 1;
            }
            0x60 | 0x64 | 0x68 => {
                let b = pop_int(&mut stack)?;
                let a = pop_int(&mut stack)?;
                let method = match op {
                    0x60 => "wrapping_add",
                    0x64 => "wrapping_sub",
                    _ => "wrapping_mul",
                };
                lines.push_str(&format!("        let t{tmp} = ({a}).{method}({b});\n"));
                stack.push(Value::Int(format!("t{tmp}")));
                tmp += 1;
            }
            0xac => {
                if ctor {
                    return Err("ireturn en constructor".into());
                }
                let value = pop_int(&mut stack)?;
                if !stack.is_empty() || r.pos != code.len() {
                    return Err("pila adicional o código posterior a ireturn".into());
                }
                lines.push_str(&format!("        {value}\n"));
                return Ok(lines);
            }
            0xb1 => {
                if !ctor || !super_called || !stack.is_empty() || r.pos != code.len() {
                    return Err("return inválido o falta constructor de Object".into());
                }
                return Ok(lines);
            }
            _ => {
                return Err(format!(
                    "objeto: opcode no soportado 0x{op:02x} en offset {start}"
                ))
            }
        }
    }
    Err("método sin return".into())
}
struct Method {
    flags: u16,
    name: String,
    desc: String,
    code: Vec<u8>,
    locals: usize,
}
fn find_interface_default(
    data: &[u8],
    requested: &str,
    wanted: &str,
) -> Result<(Vec<CpEntry>, Method)> {
    let mut r = Reader { data, pos: 0 };
    if r.u4()? != 0xcafebabe {
        return Err("interfaz no es class".into());
    }
    r.u2()?;
    r.u2()?;
    let cp = read_cp(&mut r)?;
    let flags = r.u2()?;
    let this = r.u2()?;
    r.u2()?;
    if flags & 0x0200 == 0 || class_name(&cp, this)? != requested {
        return Err("interfaz incorrecta".into());
    }
    let n = r.u2()? as usize;
    r.take(2 * n)?;
    for _ in 0..r.u2()? {
        r.take(6)?;
        skip_attrs(&mut r)?;
    }
    for _ in 0..r.u2()? {
        let flags = r.u2()?;
        let name = utf(&cp, r.u2()?)?.to_owned();
        let desc = utf(&cp, r.u2()?)?.to_owned();
        let ac = r.u2()?;
        for _ in 0..ac {
            let ai = r.u2()?;
            let len = r.u4()? as usize;
            let data = r.take(len)?;
            if name == wanted && desc == "()I" && utf(&cp, ai)? == "Code" {
                if flags & 0x0001 == 0 || flags & (0x0008 | 0x0020 | 0x0400 | 0x0100) != 0 {
                    return Err("default incompatible".into());
                }
                let mut cr = Reader { data, pos: 0 };
                cr.u2()?;
                let locals = cr.u2()? as usize;
                let len = cr.u4()? as usize;
                let code = cr.take(len)?.to_vec();
                if locals == 0 || cr.u2()? != 0 {
                    return Err("default con excepciones o locales inválidos".into());
                }
                skip_attrs(&mut cr)?;
                return Ok((
                    cp,
                    Method {
                        flags,
                        name,
                        desc,
                        code,
                        locals,
                    },
                ));
            }
        }
    }
    Err(format!("método default no encontrado: {wanted}()I"))
}
// Selección explícita: una implementación fija de un método default, no despacho JVM general.
pub(super) struct ObjectProgram {
    pub(super) source: String,
    pub(super) ctor_args: usize,
    pub(super) public_methods: Vec<(String, usize)>,
}
pub(super) fn compile_object(
    data: &[u8],
    requested: &str,
    selected: Option<(&[u8], &str, &str)>,
) -> Result<ObjectProgram> {
    let mut r = Reader { data, pos: 0 };
    if r.u4()? != 0xcafebabe {
        return Err("no es un class".into());
    }
    r.u2()?;
    r.u2()?;
    let cp = read_cp(&mut r)?;
    let flags = r.u2()?;
    let this = r.u2()?;
    let parent = r.u2()?;
    if flags & 0x0200 != 0 {
        return Err("no se admiten interfaces".into());
    }
    if class_name(&cp, this)? != requested {
        return Err("nombre de clase no coincide con ruta".into());
    }
    if class_name(&cp, parent)? != "java/lang/Object" {
        return Err("solo se admite herencia directa de Object".into());
    }
    let interfaces = r.u2()? as usize;
    let mut interface_names = Vec::new();
    for _ in 0..interfaces {
        interface_names.push(class_name(&cp, r.u2()?)?.to_owned());
    }
    let mut fields = Vec::new();
    for _ in 0..r.u2()? {
        let flags = r.u2()?;
        let n = r.u2()?;
        let d = r.u2()?;
        let name = utf(&cp, n)?;
        let desc = utf(&cp, d)?;
        if flags & 0x0008 != 0 || desc != "I" {
            return Err(format!("campo static o no int no soportado: {name}:{desc}"));
        }
        if fields.iter().any(|v| v == name) {
            return Err("campo duplicado".into());
        }
        fields.push(name.to_string());
        skip_attrs(&mut r)?;
    }
    let mut methods = Vec::new();
    for _ in 0..r.u2()? {
        let flags = r.u2()?;
        let n = r.u2()?;
        let d = r.u2()?;
        let name = utf(&cp, n)?.to_owned();
        let desc = utf(&cp, d)?.to_owned();
        if flags & 0x0008 != 0 || flags & 0x0020 != 0 || flags & 0x0400 != 0 || flags & 0x0100 != 0
        {
            return Err(format!(
                "método static, synchronized, abstract o native: {name}{desc}"
            ));
        }
        let ac = r.u2()?;
        let mut found = None;
        for _ in 0..ac {
            let an = r.u2()?;
            let len = r.u4()? as usize;
            let bytes = r.take(len)?;
            if utf(&cp, an)? == "Code" {
                let mut cr = Reader {
                    data: bytes,
                    pos: 0,
                };
                cr.u2()?;
                let locals = cr.u2()? as usize;
                let len = cr.u4()? as usize;
                let code = cr.take(len)?.to_vec();
                if cr.u2()? != 0 {
                    return Err("tabla de excepciones no soportada".into());
                }
                skip_attrs(&mut cr)?;
                found = Some(Method {
                    flags,
                    name: name.clone(),
                    desc: desc.clone(),
                    code,
                    locals,
                });
            }
        }
        methods.push(found.ok_or("método sin Code")?);
    }
    let ctors: Vec<_> = methods.iter().filter(|m| m.name == "<init>").collect();
    if ctors.len() != 1 {
        return Err("se requiere exactamente un constructor".into());
    }
    let ctor = ctors[0];
    let args = ctor
        .desc
        .strip_prefix('(')
        .and_then(|d| d.strip_suffix(")V"))
        .ok_or("constructor no soportado")?;
    if !args.bytes().all(|b| b == b'I') {
        return Err("constructor solo admite parámetros int".into());
    }
    let n = args.len();
    if ctor.locals < n + 1 {
        return Err("max_locals insuficiente".into());
    }
    let ctor_body = lower(&ctor.code, &cp, requested, &fields, true, n, None)?;
    let mut names = HashSet::new();
    let mut method_defs = String::new();
    let mut dispatch = String::new();
    let mut idx = 0;
    let mut targets: Vec<(String, usize)> = Vec::new();
    for m in methods.iter().filter(|m| m.name != "<init>") {
        if m.desc != "()I" || m.locals == 0 || !names.insert(m.name.clone()) {
            return Err(format!(
                "solo se admiten métodos instancia distintos ()I: {}{}",
                m.name, m.desc
            ));
        }
        let body = lower(&m.code, &cp, requested, &fields, false, 0, None)?;
        method_defs.push_str(&format!(
            "    pub(crate) fn method_{idx}(&mut self) -> i32 {{\n{body}    }}\n"
        ));
        dispatch.push_str(&format!(
            "            {:?} => println!(\"{{}}\", object.method_{idx}()),\n",
            m.name
        ));
        if m.flags & 0x0001 != 0 {
            targets.push((m.name.clone(), idx));
        }
        idx += 1;
    }
    if let Some((iface_data, iface_name, method_name)) = selected {
        if !interface_names.iter().any(|x| x == iface_name) {
            return Err("la clase no implementa directamente la interfaz indicada".into());
        }
        if names.contains(method_name) {
            return Err("la clase implementa el método: no se selecciona el default".into());
        }
        let (iface_cp, method) = find_interface_default(iface_data, iface_name, method_name)?;
        let body = lower(
            &method.code,
            &iface_cp,
            iface_name,
            &fields,
            false,
            0,
            Some((iface_name, &targets)),
        )?;
        method_defs.push_str(&format!(
            "    pub(crate) fn method_{idx}(&mut self) -> i32 {{\n{body}    }}\n"
        ));
        dispatch.push_str(&format!(
            "            {:?} => println!(\"{{}}\", object.method_{idx}()),\n",
            method_name
        ));
        targets.push((method_name.to_owned(), idx));
        idx += 1;
    }
    if idx == 0 {
        return Err("se requiere al menos un método instancia".into());
    }
    let struct_fields = (0..fields.len())
        .map(|i| format!("    f{i}: i32,\n"))
        .collect::<String>();
    let init_fields = (0..fields.len())
        .map(|i| format!("f{i}: 0"))
        .collect::<Vec<_>>()
        .join(", ");
    let params = (0..n)
        .map(|i| format!("a{i}: i32"))
        .collect::<Vec<_>>()
        .join(", ");
    let read_args=(0..n).map(|i|format!("    let a{i}: i32 = args[{i}].parse().unwrap_or_else(|_| {{eprintln!(\"argumento int inválido\");std::process::exit(2)}});\n")).collect::<String>();
    let pass = (0..n)
        .map(|i| format!("a{i}"))
        .collect::<Vec<_>>()
        .join(", ");
    let code=format!("// Experimento objeto: {requested}; solo incluye métodos declarados y defaults explícitos.\n\
 pub(crate) struct Object {{\n{struct_fields}}}\n\
 impl Object {{\n    fn init(&mut self, {params}) {{\n{ctor_body}    }}\n{method_defs}}}\n\
 #[allow(dead_code)]\n pub(crate) fn construct({params}) -> Object {{\n\
     let mut object=Object {{ {init_fields} }};\n     object.init({pass});\n     object\n}}\n\
 fn main() {{\n    let args:Vec<String> = std::env::args().skip(1).collect();\n\
     if args.len() < {} {{eprintln!(\"Se requieren {n} enteros y al menos un nombre de método\");std::process::exit(2);}}\n\
 {read_args}    let mut object=construct({pass});\n\
     for method in &args[{n}..] {{\n        match method.as_str() {{\n{dispatch}\
             _ => {{eprintln!(\"método no soportado: {{method}}\");std::process::exit(2);}}\n\
         }}\n    }}\n}}\n",n+1);
    Ok(ObjectProgram {
        source: code,
        ctor_args: n,
        public_methods: targets,
    })
}
