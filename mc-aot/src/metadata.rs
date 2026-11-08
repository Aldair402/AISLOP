//! Lectura estructural de clases y descriptores JVM. No verifica ni ejecuta bytecode.
use super::{bytecode, read_cp, utf, CpEntry, Reader, Result};
use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) enum Type {
    Byte,
    Char,
    Double,
    Float,
    Int,
    Long,
    Short,
    Boolean,
    Object(String),
    Array(Box<Type>),
    Void,
}
impl Type {
    fn slots(&self) -> u32 {
        match self {
            Type::Long | Type::Double => 2,
            Type::Void => 0,
            _ => 1,
        }
    }
}
fn parse_type(data: &[u8], pos: &mut usize, void_allowed: bool, depth: usize) -> Result<Type> {
    if depth > 255 {
        return Err("array supera 255 dimensiones".into());
    }
    let c = *data.get(*pos).ok_or("descriptor truncado")?;
    *pos += 1;
    Ok(match c {
        b'B' => Type::Byte,
        b'C' => Type::Char,
        b'D' => Type::Double,
        b'F' => Type::Float,
        b'I' => Type::Int,
        b'J' => Type::Long,
        b'S' => Type::Short,
        b'Z' => Type::Boolean,
        b'V' if void_allowed => Type::Void,
        b'[' => Type::Array(Box::new(parse_type(data, pos, false, depth + 1)?)),
        b'L' => {
            let begin = *pos;
            let end = data[begin..]
                .iter()
                .position(|b| *b == b';')
                .map(|i| begin + i)
                .ok_or("descriptor objeto sin ;")?;
            if begin == end
                || data[begin..end]
                    .iter()
                    .any(|b| matches!(b, b'.' | b'[' | b'(' | b')' | 0))
            {
                return Err("nombre de objeto inválido".into());
            }
            let name = std::str::from_utf8(&data[begin..end])
                .map_err(|_| "objeto UTF-8 inválido")?
                .to_owned();
            if name.starts_with('/') || name.ends_with('/') || name.contains("//") {
                return Err("nombre de objeto inválido".into());
            }
            *pos = end + 1;
            Type::Object(name)
        }
        _ => return Err(format!("tipo de descriptor inválido: 0x{c:02x}")),
    })
}
pub(super) fn field_descriptor(s: &str) -> Result<Type> {
    let mut p = 0;
    let value = parse_type(s.as_bytes(), &mut p, false, 0)?;
    if p != s.len() {
        return Err("resto en descriptor de campo".into());
    }
    Ok(value)
}
#[derive(Debug, PartialEq, Eq)]
pub(super) struct MethodDescriptor {
    pub args: Vec<Type>,
    pub returns: Type,
}
pub(super) fn method_descriptor(s: &str) -> Result<MethodDescriptor> {
    let b = s.as_bytes();
    if b.first() != Some(&b'(') {
        return Err("descriptor de método sin (".into());
    }
    let mut p = 1;
    let mut args = Vec::new();
    while b.get(p) != Some(&b')') {
        if p >= b.len() {
            return Err("descriptor de método sin )".into());
        }
        args.push(parse_type(b, &mut p, false, 0)?);
    }
    p += 1;
    let returns = parse_type(b, &mut p, true, 0)?;
    if p != b.len() {
        return Err("resto en descriptor de método".into());
    }
    Ok(MethodDescriptor { args, returns })
}
fn add_type_dependencies(ty: &Type, out: &mut BTreeSet<String>) {
    match ty {
        Type::Object(name) => {
            out.insert(name.clone());
        }
        Type::Array(inner) => add_type_dependencies(inner, out),
        _ => {}
    }
}
fn class_name(cp: &[CpEntry], i: u16) -> Result<&str> {
    match cp.get(i as usize) {
        Some(CpEntry::Class(n)) => utf(cp, *n),
        _ => Err(format!("Class inválida: {i}")),
    }
}
#[derive(Debug, Clone)]
pub(super) enum ConstantValue {
    Integer(i32),
    Float(u32),
    Long(i64),
    Double(u64),
    String(Vec<u16>),
    Other,
}
#[derive(Debug, Clone)]
pub(super) struct Field {
    pub name: String,
    pub descriptor: String,
    pub flags: u16,
    pub constant: Option<ConstantValue>,
}
#[derive(Debug)]
pub(super) struct Method {
    pub name: String,
    pub descriptor: String,
    pub flags: u16,
    pub code_len: Option<usize>,
    pub exception_handlers: usize,
    pub instructions: usize,
    pub branches: usize,
    pub argument_slots: u32,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct RecordComponent {
    pub name: String,
    pub descriptor: String,
}
#[derive(Debug)]
pub(super) struct Class {
    pub name: String,
    pub parent: Option<String>,
    pub interfaces: Vec<String>,
    pub dependencies: Vec<String>,
    pub major: u16,
    pub flags: u16,
    /// InnerClasses del propio tipo, si existe; relevante para Class.getModifiers.
    pub inner_flags: Option<u16>,
    /// None sin entrada propia; Some(None) anónima; Some(Some(nombre)) anidada/local.
    pub inner_simple_name: Option<Option<String>>,
    /// None si no hay atributo Record; Some(vec![]) para un record sin componentes.
    pub record_components: Option<Vec<RecordComponent>>,
    pub fields: Vec<Field>,
    pub methods: Vec<Method>,
}
fn skip_raw_attrs(r: &mut Reader<'_>, cp: &[CpEntry]) -> Result<()> {
    let n = r.u2()?;
    for _ in 0..n {
        let i = r.u2()?;
        utf(cp, i)?;
        let len = r.u4()? as usize;
        r.take(len)?;
    }
    Ok(())
}
pub(super) fn parse(data: &[u8]) -> Result<Class> {
    let mut r = Reader { data, pos: 0 };
    if r.u4()? != 0xcafebabe {
        return Err("magic inválido".into());
    }
    r.u2()?;
    let major = r.u2()?;
    let cp = read_cp(&mut r)?;
    let mut dependencies = BTreeSet::new();
    for entry in &cp {
        if let CpEntry::Class(i) = entry {
            let name = utf(&cp, *i)?;
            if name.starts_with('[') {
                add_type_dependencies(&field_descriptor(name)?, &mut dependencies);
            } else {
                dependencies.insert(name.to_owned());
            }
        }
    }
    for entry in &cp {
        let descriptor = match entry {
            CpEntry::NameType(_, i) | CpEntry::MethodType(i) => Some(utf(&cp, *i)?),
            _ => None,
        };
        if let Some(desc) = descriptor {
            if desc.starts_with('(') {
                let m = method_descriptor(desc)?;
                for arg in &m.args {
                    add_type_dependencies(arg, &mut dependencies);
                }
                add_type_dependencies(&m.returns, &mut dependencies);
            } else {
                add_type_dependencies(&field_descriptor(desc)?, &mut dependencies);
            }
        }
    }
    let flags = r.u2()?;
    let this = r.u2()?;
    let sup = r.u2()?;
    let name = class_name(&cp, this)?.to_owned();
    let parent = if sup == 0 {
        None
    } else {
        Some(class_name(&cp, sup)?.to_owned())
    };
    let ni = r.u2()?;
    let mut interfaces = Vec::new();
    for _ in 0..ni {
        interfaces.push(class_name(&cp, r.u2()?)?.to_owned());
    }
    let nf = r.u2()?;
    let mut fields = Vec::new();
    for _ in 0..nf {
        let flags = r.u2()?;
        let name = utf(&cp, r.u2()?)?.to_owned();
        let descriptor = utf(&cp, r.u2()?)?.to_owned();
        let field_type =
            field_descriptor(&descriptor).map_err(|e| format!("campo {name}{descriptor}: {e}"))?;
        add_type_dependencies(&field_type, &mut dependencies);
        let mut constant = None;
        let count = r.u2()?;
        for _ in 0..count {
            let attr_name = utf(&cp, r.u2()?)?;
            let len = r.u4()? as usize;
            let bytes = r.take(len)?;
            if attr_name == "ConstantValue" {
                if len != 2 || constant.is_some() {
                    return Err("atributo ConstantValue inválido".into());
                }
                let index = u16::from_be_bytes([bytes[0], bytes[1]]) as usize;
                constant = Some(match cp.get(index) {
                    Some(CpEntry::Integer(x)) => ConstantValue::Integer(*x),
                    Some(CpEntry::FloatBits(x)) => ConstantValue::Float(*x),
                    Some(CpEntry::Long(x)) => ConstantValue::Long(*x),
                    Some(CpEntry::DoubleBits(x)) => ConstantValue::Double(*x),
                    Some(CpEntry::String(u)) => match cp.get(*u as usize) {
                        Some(CpEntry::Utf8(v)) => ConstantValue::String(v.units.clone()),
                        _ => return Err("String ConstantValue inválida".into()),
                    },
                    Some(_) => ConstantValue::Other,
                    None => return Err("índice ConstantValue inválido".into()),
                });
            }
        }
        fields.push(Field {
            name,
            descriptor,
            flags,
            constant,
        });
    }
    let nm = r.u2()?;
    let mut methods = Vec::new();
    for _ in 0..nm {
        let flags = r.u2()?;
        let name = utf(&cp, r.u2()?)?.to_owned();
        let descriptor = utf(&cp, r.u2()?)?.to_owned();
        let parsed = method_descriptor(&descriptor)
            .map_err(|e| format!("método {name}{descriptor}: {e}"))?;
        let argument_slots = parsed.args.iter().map(Type::slots).sum::<u32>();
        for arg in &parsed.args {
            add_type_dependencies(arg, &mut dependencies);
        }
        add_type_dependencies(&parsed.returns, &mut dependencies);
        let nattrs = r.u2()?;
        let mut code_len = None;
        let mut exception_handlers = 0usize;
        let mut instructions = 0usize;
        let mut branches = 0usize;
        for _ in 0..nattrs {
            let attr = utf(&cp, r.u2()?)?;
            let length = r.u4()? as usize;
            let data = r.take(length)?;
            if attr == "Code" {
                if code_len.is_some() {
                    return Err("Code duplicado".into());
                }
                let mut code = Reader { data, pos: 0 };
                code.u2()?;
                code.u2()?;
                let len = code.u4()? as usize;
                let bytecode = code.take(len)?;
                let summary =
                    bytecode::scan(bytecode).map_err(|e| format!("{name}{descriptor}: {e}"))?;
                instructions = summary.instructions;
                branches = summary.branches;
                let n = code.u2()? as usize;
                for _ in 0..n {
                    let start = code.u2()? as usize;
                    let end = code.u2()? as usize;
                    let handler = code.u2()? as usize;
                    let catch_type = code.u2()?;
                    if catch_type != 0 {
                        class_name(&cp, catch_type)?;
                    }
                    bytecode::validate_handler(&summary, len, start, end, handler)
                        .map_err(|e| format!("{name}{descriptor}: {e}"))?;
                }
                skip_raw_attrs(&mut code, &cp)?;
                if code.pos != data.len() {
                    return Err("resto en Code".into());
                }
                code_len = Some(len);
                exception_handlers = n;
            }
        }
        methods.push(Method {
            name,
            descriptor,
            flags,
            code_len,
            exception_handlers,
            instructions,
            branches,
            argument_slots,
        });
    }
    let attrs=r.u2()?;
    let mut inner_flags=None;
    let mut inner_simple_name=None;
    let mut seen_inner=false;
    let mut record_components: Option<Vec<RecordComponent>> = None;
    for _ in 0..attrs {
        let attr=utf(&cp,r.u2()?)?;
        let len=r.u4()? as usize;
        let bytes=r.take(len)?;
        if attr=="Record" {
            if record_components.is_some() { return Err("Record duplicado".into()); }
            let mut sub=Reader{data:bytes,pos:0};
            let count=sub.u2()?;
            let mut components=Vec::with_capacity(count as usize);
            for _ in 0..count {
                let component_name=utf(&cp,sub.u2()?)?.to_owned();
                let descriptor=utf(&cp,sub.u2()?)?.to_owned();
                let ty=field_descriptor(&descriptor)
                    .map_err(|e| format!("componente record {component_name}{descriptor}: {e}"))?;
                add_type_dependencies(&ty, &mut dependencies);
                skip_raw_attrs(&mut sub, &cp)?;
                components.push(RecordComponent{name:component_name,descriptor});
            }
            if sub.pos!=bytes.len(){return Err("Record: longitud inválida".into());}
            record_components=Some(components);
        } else if attr=="InnerClasses" {
            if seen_inner {return Err("InnerClasses duplicado".into());}
            seen_inner=true;
            let mut sub=Reader{data:bytes,pos:0};
            let count=sub.u2()?;
            for _ in 0..count {
                let inner=sub.u2()?;let outer=sub.u2()?;let name_index=sub.u2()?;let access=sub.u2()?;
                if inner==0 {return Err("InnerClasses: clase interna inválida".into());}
                let inner_name=class_name(&cp,inner)?;
                if outer!=0 {class_name(&cp,outer)?;}
                if name_index!=0 {utf(&cp,name_index)?;}
                if inner_name==name {
                    if inner_flags.is_some(){return Err("InnerClasses: clase duplicada".into());}
                    inner_flags=Some(access);
                    inner_simple_name=Some(if name_index == 0 {None} else {Some(utf(&cp,name_index)?.to_owned())});
                }
            }
            if sub.pos!=bytes.len(){return Err("InnerClasses: longitud inválida".into());}
        }
    }
    if r.pos != data.len() {
        return Err("resto después de class".into());
    }
    dependencies.remove(&name);
    Ok(Class {
        name,
        parent,
        interfaces,
        dependencies: dependencies.into_iter().collect(),
        major,
        flags,
        inner_flags,
        inner_simple_name,
        record_components,
        fields,
        methods,
    })
}
fn walk(root: &Path, files: &mut Vec<PathBuf>) -> Result<()> {
    for entry in fs::read_dir(root).map_err(|e| format!("{}: {e}", root.display()))? {
        let entry = entry.map_err(|e| e.to_string())?;
        let kind = entry.file_type().map_err(|e| e.to_string())?;
        let path = entry.path();
        if kind.is_dir() {
            walk(&path, files)?;
        } else if kind.is_file() && path.extension().is_some_and(|x| x == "class") {
            files.push(path);
        }
    }
    Ok(())
}
fn safe(s: &str) -> String {
    s.replace(['\t', '\n', '\r'], "?")
}
pub(super) fn index_dir(path: &Path) -> Result<()> {
    let mut files = Vec::new();
    walk(path, &mut files)?;
    files.sort();
    println!("clase\tsuperclase\tversion_class\tinterfaces\tcampos\tmetodos\tmetodos_con_code\tmanejadores_excepcion\tinstrucciones\tsaltos\tdependencias_estaticas");
    let mut errors = 0;
    for file in &files {
        let result = fs::read(file)
            .map_err(|e| e.to_string())
            .and_then(|bytes| parse(&bytes));
        match result {
            Ok(c) => println!(
                "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
                safe(&c.name),
                safe(c.parent.as_deref().unwrap_or("")),
                c.major,
                c.interfaces.len(),
                c.fields.len(),
                c.methods.len(),
                c.methods.iter().filter(|m| m.code_len.is_some()).count(),
                c.methods
                    .iter()
                    .map(|m| m.exception_handlers)
                    .sum::<usize>(),
                c.methods.iter().map(|m| m.instructions).sum::<usize>(),
                c.methods.iter().map(|m| m.branches).sum::<usize>(),
                c.dependencies.len()
            ),
            Err(e) => {
                eprintln!("ERROR {}: {e}", file.display());
                errors += 1;
            }
        }
    }
    eprintln!("Archivos .class: {}; errores: {errors}", files.len());
    if errors > 0 {
        Err(format!("{errors} clases no se pudieron indexar"))
    } else {
        Ok(())
    }
}
pub(super) fn graph_dir(path: &Path) -> Result<()> {
    let mut files = Vec::new();
    walk(path, &mut files)?;
    files.sort();
    let mut errors = 0usize;
    println!("clase\tdependencia");
    for file in &files {
        match fs::read(file)
            .map_err(|e| e.to_string())
            .and_then(|data| parse(&data))
        {
            Ok(c) => {
                for dep in c.dependencies {
                    println!("{}\t{}", safe(&c.name), safe(&dep));
                }
            }
            Err(e) => {
                eprintln!("ERROR {}: {e}", file.display());
                errors += 1;
            }
        }
    }
    eprintln!("Archivos .class: {}; errores: {errors}", files.len());
    if errors > 0 {
        Err(format!("{errors} clases no se pudieron analizar"))
    } else {
        Ok(())
    }
}
/// Superficie estructural de Record; no comprueba bootstrap ni ejecuta métodos.
pub(super) fn inspect_record(data: &[u8]) -> Result<()> {
    let c = parse(data)?;
    match c.record_components {
        None => println!("record\tno"),
        Some(components) => {
            println!("record\t{}", components.len());
            for component in components {
                println!("component\t{}\t{}", safe(&component.name), safe(&component.descriptor));
            }
        }
    }
    Ok(())
}

pub(super) fn inspect(data: &[u8]) -> Result<()> {
    let c = parse(data)?;
    println!(
        "Clase: {}\nSuperclase: {}\nVersión de class: {}\nFlags: 0x{:04x}\nInterfaces: {}",
        c.name,
        c.parent.as_deref().unwrap_or("—"),
        c.major,
        c.flags,
        c.interfaces.join(", ")
    );
    println!(
        "Dependencias estáticas (CP y firmas): {}",
        c.dependencies.len()
    );
    println!("\nCampos ({}):", c.fields.len());
    for f in c.fields {
        println!("  0x{:04x} {} {}", f.flags, f.name, f.descriptor);
    }
    println!("\nMétodos ({}):", c.methods.len());
    for m in c.methods {
        println!(
            "  0x{:04x} {}{} | code={} | handlers={} | instrucciones={} | saltos={} | slots argumentos={}",
            m.flags,
            m.name,
            m.descriptor,
            m.code_len.map_or("sin Code".into(), |x| x.to_string()),
            m.exception_handlers,
            m.instructions,
            m.branches,
            m.argument_slots
        );
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_main() {
        let m = method_descriptor("([Ljava/lang/String;)V").unwrap();
        assert_eq!(
            m.args,
            vec![Type::Array(Box::new(Type::Object(
                "java/lang/String".into()
            )))]
        );
        assert_eq!(m.returns, Type::Void);
    }
    #[test]
    fn parses_primitives() {
        let m = method_descriptor("(IJFDZBCS)Ljava/lang/Object;").unwrap();
        assert_eq!(m.args.iter().map(Type::slots).sum::<u32>(), 10);
        assert!(matches!(m.returns, Type::Object(_)));
    }
    #[test]
    fn parses_nested_array() {
        assert_eq!(
            field_descriptor("[[[I").unwrap(),
            Type::Array(Box::new(Type::Array(Box::new(Type::Array(Box::new(
                Type::Int
            ))))))
        );
    }
    #[test]
    fn reject_invalid() {
        for s in [
            "",
            "(V)V",
            "(I)Vz",
            "(I",
            "()",
            "()[V",
            "(Ljava/lang/String)V",
            "(L/foo;)V",
        ] {
            assert!(method_descriptor(s).is_err(), "{s}");
        }
    }
    #[test]
    fn reject_invalid_field() {
        for s in ["V", "Ixxx", "L;", "[V", "Ljava.lang.String;"] {
            assert!(field_descriptor(s).is_err(), "{s}");
        }
    }
    #[test]
    fn reject_broken_classes() {
        assert!(parse(&[]).is_err());
        assert!(parse(&[0xca, 0xfe, 0xba, 0xbe]).is_err());
    }
}
