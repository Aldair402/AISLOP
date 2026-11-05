//! Decodificación y comprobación estructural de bytecode JVM, no verificador de tipos ni ejecución.
use super::Result;
use std::collections::HashSet;

#[derive(Debug, Default)]
pub(super) struct Summary {
    pub instructions: usize,
    pub branches: usize,
    pub boundaries: HashSet<usize>,
}
fn read_i32(code: &[u8], at: usize) -> Result<i32> {
    let x = code
        .get(at..at.checked_add(4).ok_or("overflow")?)
        .ok_or("operando truncado")?;
    Ok(i32::from_be_bytes([x[0], x[1], x[2], x[3]]))
}
fn push_target(targets: &mut Vec<i64>, start: usize, offset: i32) {
    targets.push(start as i64 + offset as i64);
}
pub(super) struct Switch {
    pub end: usize,
    pub default: i64,
    pub cases: Vec<(i32, i64)>,
}
/// Decode one JVM switch, retaining signed absolute offsets until validation.
pub(super) fn decode_switch(code: &[u8], start: usize) -> Result<Switch> {
    let op = *code.get(start).ok_or("switch fuera de rango")?;
    if op != 0xaa && op != 0xab {
        return Err("no es switch".into());
    }
    let header = start.checked_add(4).ok_or("overflow switch")? & !3;
    let target = |offset: i32| start as i64 + offset as i64;
    let default = target(read_i32(code, header)?);
    let mut cases = Vec::new();
    let end;
    if op == 0xaa {
        let low = read_i32(code, header + 4)?;
        let high = read_i32(code, header + 8)?;
        let count = high as i64 - low as i64 + 1;
        if count <= 0 || count > 65536 {
            return Err(format!("tableswitch inválido en {start}"));
        }
        let base = header.checked_add(12).ok_or("overflow switch")?;
        end = base
            .checked_add((count as usize).checked_mul(4).ok_or("overflow switch")?)
            .ok_or("overflow switch")?;
        if end > code.len() {
            return Err("tableswitch truncado".into());
        }
        for i in 0..count as usize {
            cases.push((
                (low as i64 + i as i64) as i32,
                target(read_i32(code, base + i * 4)?),
            ));
        }
    } else {
        let count = read_i32(code, header + 4)?;
        if !(0..=65536).contains(&count) {
            return Err(format!("lookupswitch inválido en {start}"));
        }
        let base = header.checked_add(8).ok_or("overflow switch")?;
        end = base
            .checked_add((count as usize).checked_mul(8).ok_or("overflow switch")?)
            .ok_or("overflow switch")?;
        if end > code.len() {
            return Err("lookupswitch truncado".into());
        }
        let mut previous = None;
        for i in 0..count as usize {
            let key = read_i32(code, base + i * 8)?;
            if previous.is_some_and(|p| key <= p) {
                return Err("lookupswitch sin claves ordenadas".into());
            }
            previous = Some(key);
            cases.push((key, target(read_i32(code, base + i * 8 + 4)?)));
        }
    }
    Ok(Switch {
        end,
        default,
        cases,
    })
}
pub(super) fn scan(code: &[u8]) -> Result<Summary> {
    if code.is_empty() || code.len() > 65535 {
        return Err("tamaño Code inválido".into());
    }
    let mut summary = Summary::default();
    let mut pc = 0usize;
    let mut targets = Vec::new();
    while pc < code.len() {
        let start = pc;
        summary.boundaries.insert(start);
        summary.instructions += 1;
        let op = code[start];
        if op > 0xc9 {
            return Err(format!("opcode reservado 0x{op:02x} en {start}"));
        }
        if op == 0xaa || op == 0xab {
            summary.branches += 1;
            let switch = decode_switch(code, start)?;
            targets.push(switch.default);
            targets.extend(switch.cases.iter().map(|(_, target)| *target));
            pc = switch.end;
            continue;
        }
        let len: usize = match op {
            0x10 | 0x12 | 0x15..=0x19 | 0x36..=0x3a | 0xa9 | 0xbc => 2,
            0x11
            | 0x13
            | 0x14
            | 0x84
            | 0x99..=0xa8
            | 0xb2..=0xb8
            | 0xbb
            | 0xbd
            | 0xc0
            | 0xc1
            | 0xc6
            | 0xc7 => 3,
            0xc5 => 4,
            0xb9 | 0xba | 0xc8 | 0xc9 => 5,
            0xc4 => {
                let child = *code.get(start + 1).ok_or("wide truncado")?;
                match child {
                    0x84 => 6,
                    0x15..=0x19 | 0x36..=0x3a | 0xa9 => 4,
                    _ => return Err(format!("wide opcode inválido 0x{child:02x}")),
                }
            }
            _ => 1,
        };
        pc = start.checked_add(len).ok_or("overflow instrucción")?;
        if pc > code.len() {
            return Err(format!("instrucción 0x{op:02x} truncada en {start}"));
        }
        if (0x99..=0xa8).contains(&op) || op == 0xc6 || op == 0xc7 {
            let offset = i16::from_be_bytes([code[start + 1], code[start + 2]]) as i32;
            push_target(&mut targets, start, offset);
            summary.branches += 1;
        } else if op == 0xc8 || op == 0xc9 {
            push_target(&mut targets, start, read_i32(code, start + 1)?);
            summary.branches += 1;
        }
        if op == 0xb9 && (code[start + 3] == 0 || code[start + 4] != 0) {
            return Err("invokeinterface inválido".into());
        }
        if op == 0xba && (code[start + 3] != 0 || code[start + 4] != 0) {
            return Err("invokedynamic inválido".into());
        }
        if op == 0xbc && !(4..=11).contains(&code[start + 1]) {
            return Err("newarray tipo inválido".into());
        }
        if op == 0xc5 && code[start + 3] == 0 {
            return Err("multianewarray sin dimensiones".into());
        }
    }
    for t in targets {
        if t < 0 || !summary.boundaries.contains(&(t as usize)) {
            return Err(format!("destino de salto inválido: {t}"));
        }
    }
    Ok(summary)
}
pub(super) fn validate_handler(
    summary: &Summary,
    len: usize,
    start: usize,
    end: usize,
    handler: usize,
) -> Result<()> {
    if start >= end
        || end > len
        || !summary.boundaries.contains(&start)
        || (end != len && !summary.boundaries.contains(&end))
        || !summary.boundaries.contains(&handler)
    {
        return Err(format!(
            "rango de excepción inválido: {start}..{end} handler {handler}"
        ));
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn validates_branches() {
        let s = scan(&[0x1a, 0x99, 0, 4, 0x03, 0xac]).unwrap();
        assert_eq!(s.instructions, 4);
        assert_eq!(s.branches, 1);
    }
    #[test]
    fn rejects_branch_to_operand() {
        assert!(scan(&[0xa7, 0, 2, 0xb1]).is_err());
    }
    #[test]
    fn rejects_truncated_and_reserved() {
        for x in [&[0xc4, 0x84, 0][..], &[0xb9, 0, 1, 0, 0][..], &[0xca][..]] {
            assert!(scan(x).is_err());
        }
    }
    #[test]
    fn validates_exception_boundaries() {
        let s = scan(&[0x03, 0xac]).unwrap();
        assert!(validate_handler(&s, 2, 0, 1, 1).is_ok());
        assert!(validate_handler(&s, 2, 0, 3, 1).is_err());
    }
    #[test]
    fn validates_tableswitch() {
        let mut code = vec![0xaa, 0, 0, 0];
        for n in [20i32, 0, 0, 20] {
            code.extend_from_slice(&n.to_be_bytes());
        }
        code.push(0xb1);
        assert!(scan(&code).is_ok());
    }
    #[test]
    fn validates_lookupswitch() {
        let mut code = vec![0xab, 0, 0, 0];
        for n in [20i32, 1, 5, 20] {
            code.extend_from_slice(&n.to_be_bytes());
        }
        code.push(0xb1);
        assert!(scan(&code).is_ok());
    }
}
