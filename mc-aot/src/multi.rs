//! Generates a small, fixed-class, single-threaded reference/dispatch experiment.
use super::{object::ObjectProgram, Result};

pub(super) fn compile_multi(
    a: &ObjectProgram,
    b: &ObjectProgram,
    reference: Option<&str>,
) -> Result<String> {
    let mut dispatch = String::new();
    for (name, i) in &a.public_methods {
        if let Some((_, j)) = b.public_methods.iter().find(|(n, _)| n == name) {
            dispatch.push_str(&format!("            {:?} => match self {{ AnyObject::A(o) => o.method_{i}(), AnyObject::B(o) => o.method_{j}(), _ => fail(\"tipo no compatible con interfaz\") }},\n", name));
        }
    }
    if dispatch.is_empty() {
        return Err("las clases no tienen métodos públicos compatibles".into());
    }
    fn args(count: usize) -> String {
        (0..count)
            .map(|_| "parse_int(next(&args, &mut pos))".to_string())
            .collect::<Vec<_>>()
            .join(", ")
    }
    let a_args = args(a.ctor_args);
    let b_args = args(b.ctor_args);
    let ref_module = reference
        .map(|s| format!("#[allow(dead_code)] mod ref_obj {{ {s} }}"))
        .unwrap_or_default();
    let ref_variants = if reference.is_some() {
        ", Text(String), RefObj(ref_obj::Target)"
    } else {
        ""
    };
    let ref_ops = if reference.is_some() {
        r#"
            "string" => { let v=next(&args,&mut pos).to_owned();let address=heap.len();heap.push(AnyObject::Text(v));let id=refs.len();refs.push(Some(address));println!("{id}"); },
            "newref" => { let s=parse_slot(next(&args,&mut pos),refs.len());let value=refs[s];
                if let Some(p)=value { if !matches!(heap.get(p),Some(AnyObject::Text(_))) { fail("se esperaba String o null"); } }
                let object=ref_obj::construct(value);let address=heap.len();heap.push(AnyObject::RefObj(object));let id=refs.len();refs.push(Some(address));println!("{id}"); },
            "getref" => { let s=parse_slot(next(&args,&mut pos),refs.len());let p=refs[s].unwrap_or_else(||fail("NullPointerException"));
                let value=match heap.get(p){Some(AnyObject::RefObj(o))=>o.get(),_=>fail("se esperaba instancia de referencia")};
                let id=refs.len();refs.push(value);println!("{id}"); },
            "text" => { let s=parse_slot(next(&args,&mut pos),refs.len());let p=refs[s].unwrap_or_else(||fail("NullPointerException"));
                match heap.get(p){Some(AnyObject::Text(s))=>println!("{s}"),_=>fail("se esperaba String")}; },
"#
    } else {
        ""
    };
    Ok(format!(
        r#"
#[allow(dead_code)] mod object_a {{ {} }}
#[allow(dead_code)] mod object_b {{ {} }}
{ref_module}
enum AnyObject {{ A(object_a::Object), B(object_b::Object){ref_variants} }}
#[allow(unreachable_patterns)]
impl AnyObject {{
    fn invoke(&mut self, name: &str) -> i32 {{
        match name {{
{dispatch}            _ => fail("método no compatible"),
        }}
    }}
}}
fn fail(message:&str) -> ! {{ eprintln!("{{message}}"); std::process::exit(2) }}
fn next<'a>(args:&'a [String], pos:&mut usize) -> &'a str {{
    let value=args.get(*pos).unwrap_or_else(|| fail("argumentos incompletos"));
    *pos+=1; value
}}
fn parse_int(value:&str) -> i32 {{ value.parse().unwrap_or_else(|_| fail("entero inválido")) }}
fn parse_slot(value:&str, n:usize) -> usize {{
    let i:usize=value.parse().unwrap_or_else(|_| fail("referencia inválida"));
    if i >= n {{ fail("referencia fuera de rango"); }} i
}}
fn main() {{
    let args:Vec<String>=std::env::args().skip(1).collect();
    let mut pos=0usize;
    let mut heap:Vec<AnyObject>=Vec::new();
    let mut refs:Vec<Option<usize>>=Vec::new();
    while pos < args.len() {{
        match next(&args,&mut pos) {{
            "new" => {{
                let ty=next(&args,&mut pos);
                let obj=match ty {{
                    "0" => AnyObject::A(object_a::construct({a_args})),
                    "1" => AnyObject::B(object_b::construct({b_args})),
                    _ => fail("tipo desconocido"),
                }};
                let address=heap.len();heap.push(obj);let slot=refs.len();refs.push(Some(address));println!("{{slot}}");
            }},
            "copy" => {{
                let slot=parse_slot(next(&args,&mut pos),refs.len());let value=refs[slot];
                let new_slot=refs.len();refs.push(value);println!("{{new_slot}}");
            }},
            "null" => {{let slot=refs.len();refs.push(None);println!("{{slot}}");}},
{ref_ops}
            "eq" => {{
                let a=parse_slot(next(&args,&mut pos),refs.len());
                let b=parse_slot(next(&args,&mut pos),refs.len());
                println!("{{}}", i32::from(refs[a]==refs[b]));
            }},
            "call" => {{
                let slot=parse_slot(next(&args,&mut pos),refs.len());let method=next(&args,&mut pos);
                let address=refs[slot].unwrap_or_else(|| fail("NullPointerException"));
                let value=heap.get_mut(address).unwrap_or_else(|| fail("referencia inválida")).invoke(method);
                println!("{{value}}");
            }},
            _ => fail("operación desconocida; usa new, copy, null, eq o call"),
        }}
    }}
}}
"#,
        a.source, b.source
    ))
}
