//! Minimal control-flow lowering: a Rust state machine, not a JVM or JIT.
use super::{arg_count, method_ref, return_expr, Compiler, CpEntry, Method, Result};
use std::collections::BTreeSet;

pub(super) fn translate_flow(
    m: &Method,
    count: usize,
    rust_name: &str,
    current_class: &str,
    return_type: char,
    ctx: &mut Compiler<'_>,
) -> Result<String> {
    if count > m.locals {
        return Err("max_locals insuficiente".into());
    }
    let mut pc = 0usize;
    let mut arms = String::new();
    let mut boundaries = BTreeSet::new();
    let mut edges: Vec<usize> = Vec::new();
    while pc < m.code.len() {
        let start = pc;
        boundaries.insert(start);
        let op = m.code[pc];
        pc += 1;
        let mut byte = || -> Result<u8> {
            let v = *m.code.get(pc).ok_or("instrucción truncada")?;
            pc += 1;
            Ok(v)
        };
        let mut branch: Option<usize> = None;
        let mut fallthrough = true;
        let op_body = match op {
            0x00 => String::new(),
            0x57 => "stack.pop().expect(\"pila vacía\");".into(),
            0x59 => "let a=*stack.last().expect(\"pila vacía\"); stack.push(a);".into(),
            0x5f => "let n=stack.len(); assert!(n >= 2, \"pila vacía\"); stack.swap(n-1,n-2);".into(),
            0x6c => "let b=stack.pop().expect(\"pila vacía\"); let a=stack.pop().expect(\"pila vacía\"); stack.push(java_int_div(a,b));".into(),
            0x91..=0x93 => {
                let ty=match op {0x91=>"i8",0x92=>"u16",_=>"i16"};
                format!("let a=stack.pop().expect(\"pila vacía\"); stack.push((a as {ty}) as i32);")
            },
            0x02..=0x08 => format!("stack.push({}i32);", op as i8 - 3),
            0x10 => format!("stack.push({}i32);", byte()? as i8),
            0x11 => { let a=byte()?; let b=byte()?; format!("stack.push({}i32);", i16::from_be_bytes([a,b])) },
            0x12 | 0x13 => {
                let index = if op == 0x12 { byte()? as u16 } else { u16::from_be_bytes([byte()?,byte()?]) };
                match m.cp.get(index as usize) { Some(CpEntry::Integer(n)) => format!("stack.push({n}i32);"), _=>return Err("ldc solo soporta int".into()) }
            },
            0x15 | 0x1a..=0x1d => {
                let i=if op==0x15 { byte()? as usize } else { (op-0x1a) as usize };
                if i>=m.locals { return Err(format!("iload fuera de rango en {start}")); }
                format!("stack.push(locals[{i}].expect(\"local sin inicializar\"));")
            },
            0x36 | 0x3b..=0x3e => {
                let i=if op==0x36 { byte()? as usize } else { (op-0x3b) as usize };
                if i>=m.locals { return Err(format!("istore fuera de rango en {start}")); }
                format!("locals[{i}] = Some(stack.pop().expect(\"pila vacía\"));")
            },
            0x84 | 0xc4 => {
                let (i,inc) = if op==0x84 { (byte()? as usize, byte()? as i8 as i16) } else {
                    if byte()? != 0x84 { return Err("wide solo admite iinc".into()); }
                    let i=u16::from_be_bytes([byte()?,byte()?]) as usize;
                    let inc=i16::from_be_bytes([byte()?,byte()?]); (i,inc)
                };
                if i>=m.locals { return Err(format!("iinc fuera de rango en {start}")); }
                format!("locals[{i}] = Some(locals[{i}].expect(\"local sin inicializar\").wrapping_add({inc}i32));")
            },
            0xb8 => {
                let index = u16::from_be_bytes([byte()?,byte()?]);
                let (class, name, desc) = method_ref(&m.cp, index)?;
                let n = arg_count(desc)?;
                let pop_args=(0..n).rev().map(|i|format!("let x{i}=stack.pop().expect(\"pila vacía\"); ")).collect::<String>();
                let args=(0..n).map(|i|format!("x{i}")).collect::<Vec<_>>().join(", ");
                let expr=match (class,name,desc) {
                    ("java/lang/Math","abs","(I)I") => "x0.wrapping_abs()".into(),
                    ("java/lang/Math","min","(II)I") => "std::cmp::min(x0,x1)".into(),
                    ("java/lang/Math","max","(II)I") => "std::cmp::max(x0,x1)".into(),
                    ("java/lang/Math","floorDiv","(II)I") => "java_floor_div(x0,x1)".into(),
                    ("java/lang/Math","floorMod","(II)I") => "java_floor_mod(x0,x1)".into(),
                    _ if class == current_class || class.starts_with("net/minecraft/") => { let target=ctx.compile_for(class,name,desc)?; format!("{target}({args})") },
                    _ => return Err(format!("invokestatic no soportado: {class}.{name}{desc} en offset {start}")),
                };
                format!("{pop_args}stack.push({expr});")
            },
            0x70 => "let b = stack.pop().expect(\"pila vacía\"); let a = stack.pop().expect(\"pila vacía\"); if b == 0 { eprintln!(\"ArithmeticException: / by zero\"); std::process::exit(2); } stack.push(a.wrapping_rem(b));".into(),
            0x60 | 0x64 | 0x68 | 0x7e | 0x80 | 0x82 => {
                let expr=match op { 0x60=>"a.wrapping_add(b)",0x64=>"a.wrapping_sub(b)",0x68=>"a.wrapping_mul(b)",0x7e=>"a & b",0x80=>"a | b",_=>"a ^ b" };
                format!("let b=stack.pop().expect(\"pila vacía\"); let a=stack.pop().expect(\"pila vacía\"); stack.push({expr});")
            },
            0x78 | 0x7a | 0x7c => {
                let expr=match op { 0x78=>"a.wrapping_shl((b as u32) & 31)", 0x7a=>"a.wrapping_shr((b as u32) & 31)", _=>"((a as u32) >> ((b as u32) & 31)) as i32" };
                format!("let b=stack.pop().expect(\"pila vacía\"); let a=stack.pop().expect(\"pila vacía\"); stack.push({expr});")
            },
            0x74 => "let a=stack.pop().expect(\"pila vacía\"); stack.push(a.wrapping_neg());".into(),
            0x99..=0xa4 | 0xa7 => {
                let displacement = i16::from_be_bytes([byte()?,byte()?]) as isize;
                let target = (start as isize).checked_add(displacement).ok_or("salto desbordado")?;
                if target < 0 { return Err("salto negativo".into()); }
                let target=target as usize; branch=Some(target);
                if op==0xa7 { fallthrough=false; format!("pc={target}; continue;") }
                else {
                    let cmp=match op { 0x99|0x9f=>"==",0x9a|0xa0=>"!=",0x9b|0xa1=>"<",0x9c|0xa2=>">=",0x9d|0xa3=>">",_=>"<=" };
                    if op<=0x9e { format!("let a=stack.pop().expect(\"pila vacía\"); if a {cmp} 0 {{ pc={target}; continue; }}") }
                    else { format!("let b=stack.pop().expect(\"pila vacía\"); let a=stack.pop().expect(\"pila vacía\"); if a {cmp} b {{ pc={target}; continue; }}") }
                }
            },
            0xaa | 0xab => {
                let switch=super::bytecode::decode_switch(&m.code, start)?;
                let default=usize::try_from(switch.default).map_err(|_| "salto switch negativo")?;
                edges.push(default);
                let mut cases=String::new();
                for (key, dest) in switch.cases {
                    let dest=usize::try_from(dest).map_err(|_| "salto switch negativo")?;
                    edges.push(dest);
                    cases.push_str(&format!("{key}i32 => {dest}usize, "));
                }
                pc=switch.end;
                fallthrough=false;
                format!("pc=match stack.pop().expect(\"pila vacía\") {{ {cases}_ => {default}usize }}; continue;")
            },
            0xc8 => {
                let displacement = i32::from_be_bytes([byte()?,byte()?,byte()?,byte()?]) as i64;
                let target=usize::try_from(start as i64 + displacement).map_err(|_| "salto negativo")?;
                branch=Some(target); fallthrough=false;
                format!("pc={target}; continue;")
            },
            0xac => { fallthrough=false; let ret=return_expr("value", return_type); format!("let value=stack.pop().expect(\"pila vacía\"); return {ret};") },
            _ => return Err(format!("opcode de flujo no soportado 0x{op:02x} en offset {start}")),
        };
        if let Some(target) = branch {
            edges.push(target);
        }
        let next = if fallthrough {
            edges.push(pc);
            format!(" pc={pc};")
        } else {
            String::new()
        };
        arms.push_str(&format!("            {start} => {{ {op_body}{next} }}\n"));
    }
    if !boundaries.contains(&0) {
        return Err("código vacío".into());
    }
    for edge in edges {
        if !boundaries.contains(&edge) {
            return Err(format!("salto o siguiente instrucción inválida: {edge}"));
        }
    }
    let params = (0..count)
        .map(|i| format!("a{i}: i32"))
        .collect::<Vec<_>>()
        .join(", ");
    let init = (0..count)
        .map(|i| format!("    locals[{i}] = Some(a{i});\n"))
        .collect::<String>();
    Ok(format!("fn {rust_name}({params}) -> i32 {{\n    let mut locals: Vec<Option<i32>> = vec![None; {}];\n{init}    let mut stack: Vec<i32> = Vec::new();\n    let mut pc: usize = 0;\n    loop {{\n        match pc {{\n{arms}            _ => panic!(\"pc inválido\"),\n        }}\n    }}\n}}\n", m.locals))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn test_flow(m: &Method) -> Result<String> {
        let mut ctx = Compiler {
            class_data: &[],
            class_name: "",
            jar: None,
            active: vec![],
            functions: vec![],
            serial: 0,
        };
        translate_flow(m, 0, "x", "", 'I', &mut ctx)
    }
    #[test]
    fn rejects_jump_into_operand() {
        let m = Method {
            code: vec![0xa7, 0, 2, 0xac],
            locals: 0,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        assert!(test_flow(&m).is_err());
    }
    #[test]
    fn rejects_fall_off() {
        let m = Method {
            code: vec![0x03],
            locals: 0,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        assert!(test_flow(&m).is_err());
    }
    #[test]
    fn translates_goto_w() {
        let m = Method {
            code: vec![0xc8, 0, 0, 0, 5, 0x03, 0xac],
            locals: 0,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        let out = test_flow(&m).unwrap();
        assert!(out.contains("pc=5; continue;"));
    }
    #[test]
    fn rejects_switch_to_middle_of_instruction() {
        let mut code = vec![0xaa, 0, 0, 0];
        for n in [20i32, 0, 0, 2] {
            code.extend_from_slice(&n.to_be_bytes());
        }
        code.extend_from_slice(&[0x03, 0xac]);
        let m = Method {
            code,
            locals: 0,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        assert!(test_flow(&m).is_err());
    }
    #[test]
    fn rejects_negative_switch_target() {
        let mut code = vec![0xab, 0, 0, 0];
        for n in [-1i32, 0] {
            code.extend_from_slice(&n.to_be_bytes());
        }
        let m = Method {
            code,
            locals: 0,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        assert!(test_flow(&m).is_err());
    }
    #[test]
    fn rejects_truncated_wide() {
        let m = Method {
            code: vec![0xc4, 0x84, 0],
            locals: 1,
            cp: vec![],
            handlers: vec![],
            synchronized: false,
        };
        assert!(test_flow(&m).is_err());
    }
}
