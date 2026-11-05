//! Traducción acotada de constructor+getter de referencia String para una clase concreta.
//! No modela java.lang.String ni el heap Java completos.
use super::{method_ref, read_cp, skip_attrs, utf, CpEntry, Reader, Result};

fn class_name(cp: &[CpEntry], i: u16) -> Result<&str> {
    match cp.get(i as usize) {
        Some(CpEntry::Class(n)) => utf(cp, *n),
        _ => Err("Class inválida".into()),
    }
}
fn field_ref(cp: &[CpEntry], i: u16) -> Result<(&str, &str, &str)> {
    let (ci, ni) = match cp.get(i as usize) {
        Some(CpEntry::FieldRef(c, n)) => (*c, *n),
        _ => return Err("Fieldref inválido".into()),
    };
    let (name, desc) = match cp.get(ni as usize) {
        Some(CpEntry::NameType(n, d)) => (*n, *d),
        _ => return Err("NameAndType inválido".into()),
    };
    Ok((class_name(cp, ci)?, utf(cp, name)?, utf(cp, desc)?))
}
#[derive(Clone)]
enum Value {
    This,
    Ref(String),
}
fn pop_this(stack: &mut Vec<Value>) -> Result<()> {
    match stack.pop() {
        Some(Value::This) => Ok(()),
        _ => Err("se esperaba this".into()),
    }
}
fn pop_ref(stack: &mut Vec<Value>) -> Result<String> {
    match stack.pop() {
        Some(Value::Ref(v)) => Ok(v),
        _ => Err("se esperaba referencia".into()),
    }
}
fn lower(code: &[u8], cp: &[CpEntry], owner: &str, field: &str, ctor: bool) -> Result<String> {
    super::bytecode::scan(code).map_err(|e| format!("bytecode inválido: {e}"))?;
    let mut r = Reader { data: code, pos: 0 };
    let mut stack: Vec<Value> = vec![];
    let mut out = String::new();
    let mut tmp = 0;
    let mut super_called = false;
    while r.pos < code.len() {
        let pc = r.pos;
        match r.u1()? {
            0x2a => stack.push(Value::This),
            0x2b if ctor => stack.push(Value::Ref("a0".into())),
            0x01 => stack.push(Value::Ref("None".into())),
            0x59 => {
                let x = stack.last().ok_or("pila vacía")?.clone();
                stack.push(x);
            }
            0xb7 => {
                let (c, n, d) = method_ref(cp, r.u2()?)?;
                if !ctor || super_called || (c, n, d) != ("java/lang/Object", "<init>", "()V") {
                    return Err(format!("constructor no soportado {c}.{n}{d}"));
                }
                pop_this(&mut stack)?;
                super_called = true;
            }
            op @ (0xb4 | 0xb5) => {
                let (c, n, d) = field_ref(cp, r.u2()?)?;
                if (c, n, d) != (owner, field, "Ljava/lang/String;") {
                    return Err(format!("campo no soportado {c}.{n}:{d}"));
                }
                if op == 0xb4 {
                    pop_this(&mut stack)?;
                    out.push_str(&format!("        let t{tmp}=self.field;\n"));
                    stack.push(Value::Ref(format!("t{tmp}")));
                    tmp += 1;
                } else {
                    let value = pop_ref(&mut stack)?;
                    pop_this(&mut stack)?;
                    out.push_str(&format!("        self.field={value};\n"));
                }
            }
            0xb0 => {
                if ctor {
                    return Err("areturn en constructor".into());
                }
                let v = pop_ref(&mut stack)?;
                if !stack.is_empty() || r.pos != code.len() {
                    return Err("pila o código residual".into());
                }
                out.push_str(&format!("        {v}\n"));
                return Ok(out);
            }
            0xb1 => {
                if !ctor || !super_called || !stack.is_empty() || r.pos != code.len() {
                    return Err("constructor inválido".into());
                }
                return Ok(out);
            }
            x => return Err(format!("opcode no soportado 0x{x:02x} en {pc}")),
        }
    }
    Err("método sin retorno".into())
}
struct Method {
    name: String,
    desc: String,
    flags: u16,
    code: Vec<u8>,
    locals: usize,
}
pub(super) fn compile_reference(
    data: &[u8],
    wanted_class: &str,
    wanted_getter: &str,
) -> Result<String> {
    let mut r = Reader { data, pos: 0 };
    if r.u4()? != 0xcafebabe {
        return Err("no es .class".into());
    }
    r.u2()?;
    r.u2()?;
    let cp = read_cp(&mut r)?;
    let class_flags = r.u2()?;
    let ci = r.u2()?;
    let pi = r.u2()?;
    if class_flags & (0x0200 | 0x0400) != 0
        || class_name(&cp, ci)? != wanted_class
        || class_name(&cp, pi)? != "java/lang/Object"
    {
        return Err("se requiere clase concreta que herede directamente de Object".into());
    }
    let ifaces = r.u2()? as usize;
    r.take(ifaces * 2)?;
    let mut fields = vec![];
    for _ in 0..r.u2()? {
        let flags = r.u2()?;
        let name = utf(&cp, r.u2()?)?.to_owned();
        let desc = utf(&cp, r.u2()?)?.to_owned();
        if flags & 0x8 != 0 || desc != "Ljava/lang/String;" {
            return Err("solo se admite un campo instancia String".into());
        }
        fields.push(name);
        skip_attrs(&mut r)?;
    }
    if fields.len() != 1 {
        return Err("se requiere exactamente un campo String".into());
    }
    let mut methods = vec![];
    for _ in 0..r.u2()? {
        let flags = r.u2()?;
        let name = utf(&cp, r.u2()?)?.to_owned();
        let desc = utf(&cp, r.u2()?)?.to_owned();
        let attrs = r.u2()?;
        for _ in 0..attrs {
            let nameidx = r.u2()?;
            let len = r.u4()? as usize;
            let data = r.take(len)?;
            if utf(&cp, nameidx)? == "Code"
                && ((name == "<init>" && desc == "(Ljava/lang/String;)V")
                    || (name == wanted_getter && desc == "()Ljava/lang/String;"))
            {
                if flags & (0x8 | 0x20 | 0x100 | 0x400) != 0 {
                    return Err("static/synchronized/native/abstract no soportado".into());
                }
                let mut code = Reader { data, pos: 0 };
                code.u2()?;
                let locals = code.u2()? as usize;
                let len = code.u4()? as usize;
                let body = code.take(len)?.to_vec();
                if code.u2()? != 0 {
                    return Err("excepciones no soportadas".into());
                }
                skip_attrs(&mut code)?;
                methods.push(Method {
                    name: name.clone(),
                    desc: desc.clone(),
                    flags,
                    code: body,
                    locals,
                });
            }
        }
        if name == "<clinit>" {
            return Err("inicializador de clase no soportado".into());
        }
    }
    let ctors: Vec<_> = methods.iter().filter(|m| m.name == "<init>").collect();
    let gets: Vec<_> = methods.iter().filter(|m| m.name == wanted_getter).collect();
    if ctors.len() != 1 || gets.len() != 1 {
        return Err("constructor o getter no encontrados de forma única".into());
    }
    let ctor = ctors[0];
    let getter = gets[0];
    if ctor.locals < 2
        || getter.locals < 1
        || getter.flags & 1 == 0
        || getter.desc != "()Ljava/lang/String;"
    {
        return Err("métodos incompatibles".into());
    }
    let init = lower(&ctor.code, &cp, wanted_class, &fields[0], true)?;
    let get = lower(&getter.code, &cp, wanted_class, &fields[0], false)?;
    let preamble=format!("// Constructor y getter de referencia traducidos de {wanted_class}; no es una clase completa.\n");
    Ok(format!(
        r#"{preamble}
pub(crate) struct Target {{ field:Option<usize> }}
impl Target {{
    fn init(&mut self,a0:Option<usize>) {{
{init}    }}
    pub(crate) fn get(&self)->Option<usize> {{
{get}    }}
}}
#[allow(dead_code)]
pub(crate) fn construct(a0:Option<usize>)->Target {{let mut obj=Target{{field:None}};obj.init(a0);obj}}
enum Object {{ String(String), Target(Target) }}
fn fail(msg:&str)->! {{eprintln!("{{msg}}");std::process::exit(2)}}
fn next<'a>(args:&'a [String],i:&mut usize)->&'a str {{let s=args.get(*i).unwrap_or_else(||fail("argumentos incompletos"));*i+=1;s}}
fn slot(s:&str,n:usize)->usize {{let i:usize=s.parse().unwrap_or_else(|_|fail("referencia inválida"));if i>=n{{fail("referencia fuera de rango")}}i}}
fn main() {{
    let args:Vec<String>=std::env::args().skip(1).collect();let mut i=0;
    let mut heap:Vec<Object>=vec![];let mut refs:Vec<Option<usize>>=vec![];
    while i<args.len() {{
        match next(&args,&mut i) {{
            "string"=>{{let s=next(&args,&mut i).to_owned();let addr=heap.len();heap.push(Object::String(s));let id=refs.len();refs.push(Some(addr));println!("{{id}}");}},
            "null"=>{{let id=refs.len();refs.push(None);println!("{{id}}");}},
            "copy"=>{{let id=slot(next(&args,&mut i),refs.len());let v=refs[id];let out=refs.len();refs.push(v);println!("{{out}}");}},
            "new"=>{{
                let id=slot(next(&args,&mut i),refs.len());let v=refs[id];
                if let Some(p)=v {{if !matches!(heap.get(p),Some(Object::String(_))){{fail("se esperaba String o null")}}}}
                let mut object=Target{{field:None}};object.init(v);
                let addr=heap.len();heap.push(Object::Target(object));let out=refs.len();refs.push(Some(addr));println!("{{out}}");
            }},
            "get"=>{{let id=slot(next(&args,&mut i),refs.len());let p=refs[id].unwrap_or_else(||fail("NullPointerException"));
                let v=match heap.get(p){{Some(Object::Target(o))=>o.get(),_=>fail("se esperaba instancia destino")}};
                let out=refs.len();refs.push(v);println!("{{out}}");
            }},
            "eq"=>{{let a=slot(next(&args,&mut i),refs.len());let b=slot(next(&args,&mut i),refs.len());println!("{{}}",i32::from(refs[a]==refs[b]));}},
            "text"=>{{let id=slot(next(&args,&mut i),refs.len());let p=refs[id].unwrap_or_else(||fail("NullPointerException"));
                match heap.get(p){{Some(Object::String(s))=>println!("{{s}}"),_=>fail("se esperaba String")}}
            }},
            _=>fail("operación desconocida; usa string, null, copy, new, get, eq o text"),
        }}
    }}
}}
"#
    ))
}
