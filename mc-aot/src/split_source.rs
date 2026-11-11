//! split_source — divide el fuente monolítico que emite mc-aot en un workspace
//! Cargo de crates pequeños (base + `layer1_N` + bin) para que rustc no agote
//! la memoria del sandbox (cargo con CARGO_BUILD_JOBS=1).
//!
//! Reglas de partición (invariantes):
//!   base    -> TODOS los items no-fn (const/static/struct/enum/trait/
//!             macro_rules!), TODOS los `thread_local!` (pub) y TODOS los
//!             `impl` (tipos y traits viven en base; coherence y el orphan
//!             rule obligan a que los impls estén en el crate que define la
//!             colección o el trait) + el cierre fijo de fns cuyo cuerpo solo
//!             menciona nombres de base (p.ej. `clear_publish_session`);
//!   layer1_N-> resto de fns, en orden topológico (callees primero tras SCC +
//!             DAG de condensación), empaquetadas greedy en crates de <=
//!             BIND_CAP bytes; las aristas (nombre, llamada o referencia de
//!             tipo/path) apuntan a crates anteriores, sin ciclos;
//!   bin     -> `fn main`/`fn main_inner` crudos; depende de todos los crates.
//! Cada crate no-bin hace `use base::*;` + `use layer1_i::*;` de los locales
//! anteriores; deps = base + layer1_i(i < k). Emite un workspace listo para
//! `cargo build` (resolver=2, flate2=1.0.35, [profile.dev] sin debuginfo ni
//! incremental para no duplicar RAM).
use std::collections::HashMap;

const BIND_CAP: usize = 1_400_000;
const ALLOW: &str = "#![allow(dead_code,unused_variables,unused_mut)]\n";

#[derive(Clone, Copy, PartialEq, Eq)]
enum Kind {
    Fn,
    Const,
    Static,
    Struct,
    Enum,
    Trait,
    Impl,
    MacroRules,
    Bin,
    ThreadLocal,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum NodeClass {
    Base, // consts/statics/structs/enums/traits/macro_rules
    ThreadLocal,
    Impl,
    Fn,
}

struct Item {
    kind: Kind,
    start: usize, // lines idx (inclusive, attributes back-scanned)
    end: usize,   // lines idx (exclusive)
    names: Vec<String>, // nombres declarados: fn → 1, const/static/struct/enum/trait → 1, thread_local → N estáticos
}

fn is_pure_attr_line(l: &str) -> bool {
    let t = l.trim();
    t.starts_with("#[") && t.ends_with(']') && !t.contains(';')
}

/// Parsea una línea de nivel superior con la forma [attrs] [pub] <kw> ...
/// Devuelve el offset (bytes) donde arranca la keyword y el tipo.
fn parse_item_line(l: &str) -> Option<(usize, Kind)> {
    let b = l.as_bytes();
    let mut i = 0usize;
    loop {
        if l[i..].starts_with("#[") {
            let mut depth = 0i32;
            let mut j = i + 1;
            while j < b.len() {
                match b[j] {
                    b'[' => depth += 1,
                    b']' => {
                        depth -= 1;
                        if depth == 0 {
                            j += 1;
                            break;
                        }
                    }
                    _ => {}
                }
                j += 1;
            }
            i = j;
            while i < b.len() && b[i] == b' ' {
                i += 1;
            }
            continue;
        }
        break;
    }
    if l[i..].starts_with("pub(") {
        let mut depth = 0i32;
        let mut j = i + 3;
        while j < b.len() {
            match b[j] {
                b'(' => depth += 1,
                b')' => {
                    depth -= 1;
                    if depth == 0 {
                        j += 1;
                        break;
                    }
                }
                _ => {}
            }
            j += 1;
        }
        i = j;
        while i < b.len() && b[i] == b' ' {
            i += 1;
        }
    } else if l[i..].starts_with("pub ") {
        i += 4;
    }
    let rest = &l[i..];
    for (kw, kind) in [
        ("fn", Kind::Fn),
        ("const", Kind::Const),
        ("static", Kind::Static),
        ("struct", Kind::Struct),
        ("enum", Kind::Enum),
        ("trait", Kind::Trait),
        ("impl", Kind::Impl),
        ("macro_rules!", Kind::MacroRules),
    ] {
        if let Some(after) = rest.strip_prefix(kw) {
            let ok = kw == "macro_rules!"
                || after.is_empty()
                || after.chars().next().map(|c| !c.is_ascii_alphanumeric() && c != '_').unwrap_or(true);
            if ok {
                return Some((i, kind));
            }
        }
    }
    None
}

/// Primer identificador tras `fn ` en la línea.
fn fn_name_of(l: &str, kind_off: usize) -> Option<String> {
    let rest = &l[kind_off + 2..]; // after "fn"
    let trimmed = rest.trim_start_matches([' ', '\t']);
    let name: String = trimmed
        .chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
        .collect();
    if name.is_empty() {
        None
    } else {
        Some(name)
    }
}

/// Tokens `ident` dentro de `source[start..end]`. Si `calls_only`, solo los
/// seguidos (módulo espacios/saltos) de `(`.
/// Líneas y offsets de byte acumulados (fin exclusivo por línea: len+1 por '\n').
fn line_offsets(source: &str) -> (Vec<&str>, Vec<usize>) {
    let lines: Vec<&str> = source.split('\n').collect();
    let mut offs = Vec::with_capacity(lines.len() + 1);
    let mut acc = 0usize;
    for l in &lines {
        offs.push(acc);
        acc += l.len() + 1;
    }
    offs.push(acc);
    (lines, offs)
}

fn ident_tokens(source: &str, start: usize, end: usize, calls_only: bool) -> Vec<usize> {
    let b = source.as_bytes();
    let mut out = Vec::new();
    let mut i = start;
    while i < end {
        let c = b[i];
        if c == b'_' || c.is_ascii_alphabetic() {
            let s = i;
            while i < end && (b[i] == b'_' || b[i].is_ascii_alphanumeric()) {
                i += 1;
            }
            if calls_only {
                let mut j = i;
                while j < end && (b[j] == b' ' || b[j] == b'\t' || b[j] == b'\n' || b[j] == b'\r') {
                    j += 1;
                }
                if j < end && b[j] == b'(' {
                    out.push(s);
                }
            } else {
                out.push(s);
            }
        } else {
            i += 1;
        }
    }
    out
}

/// Nombre declarado del item en la línea del keyword (const/static/struct/enum/
/// trait/macro_rules!/fn). La keyword no contiene identificadores, así que tras
/// el prefijo viene [mut] ident.
fn item_decl_name(line: &str, kind: Kind) -> Option<String> {
    let (off, _) = parse_item_line(line)?;
    let kw_len = match kind {
        Kind::Fn => 2,
        Kind::Const => 5,
        Kind::Static => 6,
        Kind::Struct => 6,
        Kind::Enum => 4,
        Kind::Trait => 5,
        Kind::MacroRules => 12,
        _ => return None,
    };
    let mut rest = line[off + kw_len..].trim_start_matches([' ', '\t']);
    if let Some(r) = rest.strip_prefix("mut ") {
        rest = r.trim_start();
    }
    let name: String = rest
        .chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
        .collect();
    if name.is_empty() {
        None
    } else {
        Some(name)
    }
}

/// Estáticos declarados dentro de un bloque `thread_local!` (puede haber más de
/// uno, p.ej. `thread_local! { static A: ...; static B: ... }`); vale para las
/// formas multilínea habituales del código generado.
fn thread_local_names(lines: &[&str], s: usize, e: usize) -> Vec<String> {
    let mut out = Vec::new();
    for j in s..e {
        let l = lines[j];
        let mut rest = l;
        while let Some(pos) = rest.find("static") {
            let after = &rest[pos + 6..];
            let trimmed = after.trim_start_matches([' ', '\t']);
            if (after.len() != trimmed.len() || trimmed.starts_with(' '))
                && !trimmed.is_empty()
            {
                // asegurarse de que va tras un separador ({ ; ,) o al inicio con pub
                let before = &rest[..pos];
                let sep_ok = before.is_empty()
                    || before.trim_end().ends_with('{')
                    || before.trim_end().ends_with(';')
                    || before.trim_end().ends_with("pub ")
                    || before.trim_end().ends_with("pub(crate) ");
                if sep_ok {
                    let name: String = trimmed
                        .chars()
                        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
                        .collect();
                    if !name.is_empty() {
                        out.push(name);
                    }
                }
            }
            rest = &rest[pos + 6..];
        }
    }
    out.sort_unstable();
    out.dedup();
    out
}

fn tarjan_scc(adj: &[Vec<usize>]) -> Vec<Vec<usize>> {
    let n = adj.len();
    let mut index = vec![u32::MAX; n];
    let mut low = vec![u32::MAX; n];
    let mut onstack = vec![false; n];
    let mut stack: Vec<usize> = Vec::new();
    let mut comps: Vec<Vec<usize>> = Vec::new();
    let mut counter = 0u32;
    for s in 0..n {
        if index[s] != u32::MAX {
            continue;
        }
        let mut work: Vec<(usize, usize)> = vec![(s, 0)];
        while let Some((node, mut pi)) = work.pop() {
            if pi == 0 {
                index[node] = counter;
                low[node] = counter;
                counter += 1;
                stack.push(node);
                onstack[node] = true;
            }
            let mut recursed = false;
            while pi < adj[node].len() {
                let w = adj[node][pi];
                if index[w] == u32::MAX {
                    work.push((node, pi + 1));
                    work.push((w, 0));
                    recursed = true;
                    break;
                } else if onstack[w] {
                    low[node] = low[node].min(index[w]);
                }
                pi += 1;
            }
            if recursed {
                continue;
            }
            if low[node] == index[node] {
                let mut scc = Vec::new();
                loop {
                    let w = stack.pop().expect("tarjan stack");
                    onstack[w] = false;
                    scc.push(w);
                    if w == node {
                        break;
                    }
                }
                comps.push(scc);
            }
            if let Some(&(parent, _)) = work.last() {
                low[parent] = low[parent].min(low[node]);
            }
        }
    }
    comps
}

/// Orden topológico de componentes: callees primero (por profundidad creciente
/// medida como 1 + max profundidad de hijos del DAG de condensación).
fn topo_callees_first(adj: &[Vec<usize>], comps: &[Vec<usize>]) -> Vec<usize> {
    let w = comps.len();
    let mut comp_of = vec![usize::MAX; adj.len()];
    for (ci, comp) in comps.iter().enumerate() {
        for &v in comp {
            comp_of[v] = ci;
        }
    }
    let mut dags: Vec<Vec<usize>> = vec![Vec::new(); w];
    for (v, outs) in adj.iter().enumerate() {
        for &u in outs {
            if comp_of[v] != comp_of[u] {
                dags[comp_of[v]].push(comp_of[u]);
            }
        }
    }
    for d in dags.iter_mut() {
        d.sort_unstable();
        d.dedup();
    }
    // profundidad iterativa con memoización
    let mut depth = vec![u32::MAX; w];
    for c in 0..w {
        if depth[c] != u32::MAX {
            continue;
        }
        let mut stack_ = vec![(c, false)];
        while let Some((node, processed)) = stack_.pop() {
            if processed {
                let mut lv = 1u32;
                for &ch in &dags[node] {
                    lv = lv.max(depth[ch] + 1);
                }
                depth[node] = lv;
                continue;
            }
            if depth[node] != u32::MAX {
                continue;
            }
            stack_.push((node, true));
            for &ch in &dags[node] {
                if depth[ch] == u32::MAX {
                    stack_.push((ch, false));
                }
            }
        }
    }
    let mut order: Vec<usize> = (0..w).collect();
    order.sort_by_key(|&c| depth[c]);
    order
}

/// pub-ifia la primera línea de un item según `kinds` (para el crate base y
/// los crates layer1_N).
fn pub_prefix_line(l: &str, kinds: &[&str]) -> String {
    let (kind_off, kind) = match parse_item_line(l) {
        Some(x) => x,
        None => return l.to_string(),
    };
    let kw = match kind {
        Kind::Fn => "fn",
        Kind::Const => "const",
        Kind::Static => "static",
        Kind::Struct => "struct",
        Kind::Enum => "enum",
        Kind::Trait => "trait",
        _ => return l.to_string(),
    };
    if !kinds.contains(&kw) {
        return l.to_string();
    }
    // ya era pub?
    let before = &l[..kind_off];
    if before.trim_end().ends_with("pub") || before.trim_end().ends_with(')') && before.contains("pub") {
        return l.to_string();
    }
    let mut out = String::with_capacity(l.len() + 4);
    out.push_str(&l[..kind_off]);
    out.push_str("pub ");
    out.push_str(&l[kind_off..]);
    out
}

/// Inserta `pub ` antes de cada campo `ident:` en la línea (usado en structs).
fn pubify_struct_fields(l: &str) -> String {
    let b = l.as_bytes();
    let mut out = String::with_capacity(l.len() + 16);
    let mut i = 0usize;
    let mut last = 0usize;
    while i < b.len() {
        if b[i] == b'{' || b[i] == b',' {
            let j = i + 1;
            let mut k = j;
            while k < b.len() && b[k] == b' ' {
                k += 1;
            }
            let ws_end = k;
            while k < b.len() && (b[k] == b'_' || b[k].is_ascii_alphanumeric()) {
                k += 1;
            }
            let ident_end = k;
            if k > ws_end {
                let mut m = ident_end;
                while m < b.len() && b[m] == b' ' {
                    m += 1;
                }
                if m < b.len() && b[m] == b':' {
                    out.push_str(&l[last..j]); // incluye '{' o ','
                    out.push_str(" pub ");
                    out.push_str(&l[ws_end..ident_end]); // ident
                    out.push_str(&l[ident_end..m]);      // espacios antes de ':'
                    out.push(':');
                    last = m + 1;
                    i = m + 1;
                    continue;
                }
            }
        }
        i += 1;
    }
    if last == 0 {
        return l.to_string();
    }
    out.push_str(&l[last..]);
    out
}

/// Pub-ifia campos de struct en línea suelta `  nombre: Tipo,` (sin llave ni coma previa).
fn pubify_leading_field(l: &str) -> String {
    let trimmed = l.trim_start();
    let first = trimmed.chars().next();
    match first {
        Some(c) if c.is_ascii_lowercase() || c == '_' => {}
        _ => return l.to_string(),
    }
    let ident_len: usize = trimmed
        .chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
        .map(|c| c.len_utf8())
        .sum();
    let after = trimmed[ident_len..].trim_start_matches(' ');
    if after.starts_with(':') && !after.starts_with("::") {
        // evitar caso `pub nombre:` ya formateado o `nombre::type` (?) no suele darse
        let indent = &l[..l.len() - trimmed.len()];
        return format!("{indent}pub {}", trimmed);
    }
    l.to_string()
}

/// Emite las líneas de un item con las transformaciones de pub-ificación.
fn emit_item(lines: &[&str], item: &Item, skip: &[bool], is_base: bool) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut in_struct = false;
    let mut inherent_impl = false;
    for j in item.start..item.end {
        if skip[j] {
            continue;
        }
        let l = lines[j];
        if l.starts_with("impl") {
            let header = l.split('{').next().unwrap_or(l);
            inherent_impl = !header.contains(" for ");
            out.push(l.to_string());
            continue;
        }
        if inherent_impl && {
            let t = l.trim_start();
            t.starts_with("fn ")
        } {
            let indent_len = l.len() - l.trim_start().len();
            let mut s = String::with_capacity(l.len() + 4);
            s.push_str(&l[..indent_len]);
            s.push_str("pub ");
            s.push_str(l[indent_len..].trim_start());
            out.push(s);
            continue;
        }
        if parse_item_line(l).map(|(_, k)| k == Kind::Struct).unwrap_or(false) {
            let l2 = pub_prefix_line(l, &["struct"]);
            let l2 = pubify_struct_fields(&l2);
            if l2.contains('{') && !l2.contains('}') {
                in_struct = true;
            }
            out.push(l2);
            continue;
        }
        if in_struct {
            if l.trim_end().ends_with('}') {
                in_struct = false;
                out.push(l.to_string());
                continue;
            }
            let mut l2 = pubify_struct_fields(l);
            if l2 == l {
                l2 = pubify_leading_field(l);
            }
            out.push(l2);
            continue;
        }
        if let Some((_, _)) = parse_item_line(l) {
            if is_base {
                out.push(pub_prefix_line(l, &["fn", "const", "static", "struct", "enum", "trait"]));
            } else {
                out.push(pub_prefix_line(l, &["fn"]));
            }
            continue;
        }
        out.push(l.to_string());
    }
    out
}

fn span_bytes(lines: &[&str], item: &Item) -> usize {
    lines[item.start..item.end].iter().map(|l| l.len() + 1).sum()
}

/// Item de `thread_local!`: emite el bloque crudo pero con los estáticos `pub`
/// (el crate `base` los exporta; los crates de fns los importan con `use base::*`).
fn emit_thread_local(lines: &[&str], item: &Item) -> Vec<String> {
    let mut out = Vec::with_capacity(item.end - item.start);
    for j in item.start..item.end {
        let l = lines[j];
        // primer `static ` declarado en la línea -> `pub static `
        if let Some(pos) = l.find("static ") {
            if !l.contains("pub static") {
                let mut s2 = String::with_capacity(l.len() + 4);
                s2.push_str(&l[..pos]);
                s2.push_str("pub ");
                s2.push_str(&l[pos..]);
                out.push(s2);
                continue;
            }
        }
        out.push(l.to_string());
    }
    out
}

/// Reescribe `ident` en `source[pos..]` devolviendo su rango.
fn token_bounds(source: &str, pos: usize) -> (usize, usize) {
    let b = source.as_bytes();
    let mut i = pos;
    while i < b.len() && (b[i] == b'_' || b[i].is_ascii_alphanumeric()) {
        i += 1;
    }
    (pos, i)
}

/// Divide `source` en trabajo de partición concreto (consumible por emit).
struct Partition {
    files: Vec<(String, String)>,         // relpath, contents
}

fn partition(source: &str) -> Result<Partition, String> {
    let lines: Vec<&str> = source.split('\n').collect();
    let n_lines = lines.len();
    let (_, offs) = line_offsets(source);

    // ---- thread_local! blocks: son items de primera clase (van a base) ------
    let mut tl_spans: Vec<(usize, usize)> = Vec::new();
    let mut shadow = vec![false; n_lines];
    {
        let mut i = 0usize;
        while i < n_lines {
            if lines[i].starts_with("thread_local!") {
                let start = i;
                let mut depth = 0i64;
                let mut j = i;
                let mut closed = false;
                while j < n_lines {
                    for c in lines[j].chars() {
                        match c {
                            '{' => depth += 1,
                            '}' => depth -= 1,
                            _ => {}
                        }
                    }
                    j += 1;
                    if depth <= 0 {
                        closed = true;
                        break;
                    }
                }
                if !closed {
                    return Err(format!("thread_local! en línea {} sin cerrar", start + 1));
                }
                for slot in shadow.iter_mut().take(j).skip(start) {
                    *slot = true;
                }
                tl_spans.push((start, j));
                i = j;
            } else {
                i += 1;
            }
        }
    }

    // ---- candidatos de items (nivel superior) -------------------------------
    let mut kw: Vec<(usize, Kind)> = Vec::new();
    for idx in 0..n_lines {
        if shadow[idx] {
            continue;
        }
        if let Some((_, kind)) = parse_item_line(lines[idx]) {
            kw.push((idx, kind));
        }
    }
    let n_items = kw.len();
    let mut starts: Vec<usize> = Vec::with_capacity(n_items);
    for &(line, _) in &kw {
        let mut b = line;
        while b > 0 && is_pure_attr_line(lines[b - 1]) && !shadow[b - 1] {
            b -= 1;
        }
        starts.push(b);
    }
    let mut items: Vec<Item> = Vec::with_capacity(n_items + tl_spans.len());
    for (j, &(line, kind)) in kw.iter().enumerate() {
        let start = starts[j];
        let end = if j + 1 < n_items { starts[j + 1] } else { n_lines };
        let names = match kind {
            Kind::Impl => Vec::new(),
            _ => item_decl_name(lines[line], kind).into_iter().collect(),
        };
        let kind = match kind {
            Kind::Fn if matches!(names.first().map(String::as_str), Some("main") | Some("main_inner")) => Kind::Bin,
            other => other,
        };
        items.push(Item { kind, start, end, names });
    }
    for &(s, e) in &tl_spans {
        items.push(Item { kind: Kind::ThreadLocal, start: s, end: e, names: thread_local_names(&lines, s, e) });
    }
    items.sort_unstable_by_key(|it| it.start);

    // ---- grafo de llamadas entre slots de fns no-Bin ------------------------
    let fn_item_indices: Vec<usize> = (0..items.len()).filter(|&i| items[i].kind == Kind::Fn).collect();
    let bin_item_indices: Vec<usize> = (0..items.len()).filter(|&i| items[i].kind == Kind::Bin).collect();
    let slot_of_item: HashMap<usize, usize> = fn_item_indices.iter().enumerate().map(|(k, &v)| (v, k)).collect();
    let mut fn_name_map: HashMap<&str, Vec<usize>> = HashMap::new();
    for &idx in &fn_item_indices {
        if let Some(n) = items[idx].names.first() {
            fn_name_map.entry(n.as_str()).or_default().push(idx);
        }
    }
    // adjacencia slot->slot (calls); el SCC sobre F' se usa para el cierre
    let nf = fn_item_indices.len();
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); nf];
    {
        let mut sorted_fns: Vec<(usize, usize, usize)> = fn_item_indices
            .iter()
            .map(|&idx| (offs[items[idx].start], offs[items[idx].end], idx))
            .collect();
        sorted_fns.sort_by_key(|&(s, _, _)| s);
        let tokens = ident_tokens(source, 0, source.len(), true);
        for s in tokens {
            let (_, te) = token_bounds(source, s);
            let name = &source[s..te];
            let owners = match fn_name_map.get(name) {
                Some(o) => o,
                None => continue,
            };
            let pos = match sorted_fns.binary_search_by_key(&s, |&(bs, _, _)| bs) {
                Ok(p) => p,
                Err(0) => continue,
                Err(p) => p - 1,
            };
            let (bs, be, caller_item) = sorted_fns[pos];
            if s < bs || s >= be {
                continue;
            }
            let caller_slot = slot_of_item[&caller_item];
            for &owner in owners {
                if owner != caller_item {
                    adj[caller_slot].push(slot_of_item[&owner]);
                }
            }
        }
    }
    for a in adj.iter_mut() {
        a.sort_unstable();
        a.dedup();
    }

    // ---- SCC sobre TODAS las fns (base para el cierre fijo) -----------------
    let comps = tarjan_scc(&adj);
    let mut comp_of_slot = vec![usize::MAX; nf];
    for (ci, comp) in comps.iter().enumerate() {
        for &slot in comp {
            comp_of_slot[slot] = ci;
        }
    }
    // orden topológico (callees primero)
    let pack_order = topo_callees_first(&adj, &comps);

    // ---- cierre fijo MÍNIMO de base: semillas = F-fns referenciados por impls
    // y thread_locals (van a base); luego se arrastra la clausura de callees
    // (base no puede depender de crates de fns posteriores).
    let comp_dag_adj: Vec<Vec<usize>> = {
        let mut d: Vec<Vec<usize>> = vec![Vec::new(); comps.len()];
        let mut tmp: Vec<std::collections::HashSet<usize>> = vec![std::collections::HashSet::new(); comps.len()];
        for slot in 0..nf {
            let ci = comp_of_slot[slot];
            for &callee in &adj[slot] {
                let cj = comp_of_slot[callee];
                if cj != ci {
                    tmp[ci].insert(cj);
                }
            }
        }
        for (ci, set) in tmp.into_iter().enumerate() {
            d[ci] = set.into_iter().collect();
        }
        d
    };
    let mut movable = vec![false; comps.len()];
    let mut seeds: Vec<usize> = Vec::new();
    for idx in 0..items.len() {
        if !matches!(items[idx].kind, Kind::Impl | Kind::ThreadLocal) {
            continue;
        }
        let (bs, be) = (offs[items[idx].start], offs[items[idx].end]);
        for s in ident_tokens(source, bs, be, true) {
            let (_, te) = token_bounds(source, s);
            let name = &source[s..te];
            if let Some(owners) = fn_name_map.get(name) {
                for &o in owners {
                    seeds.push(comp_of_slot[slot_of_item[&o]]);
                }
            }
        }
    }
    let mut stack = seeds;
    while let Some(ci) = stack.pop() {
        if movable[ci] {
            continue;
        }
        movable[ci] = true;
        for &cj in &comp_dag_adj[ci] {
            if !movable[cj] {
                stack.push(cj);
            }
        }
    }

    // comps que quedan en los crates de fns, en orden topológico (callees primero)
    let low_comp_order: Vec<usize> = pack_order.into_iter().filter(|&ci| !movable[ci]).collect();

    // ---- empaquetado greedy de las comps de F' -------------------------------
    let mut fn_bytes = vec![0usize; comps.len()];
    for (ci, comp) in comps.iter().enumerate() {
        fn_bytes[ci] = comp
            .iter()
            .map(|&slot| span_bytes(&lines, &items[fn_item_indices[slot]]))
            .sum();
    }
    let mut low_crates: Vec<Vec<usize>> = Vec::new();
    let mut cur: Vec<usize> = Vec::new();
    let mut cur_bytes = 0usize;
    for &ci in &low_comp_order {
        let sz = fn_bytes[ci];
        if !cur.is_empty() && cur_bytes + sz > BIND_CAP {
            low_crates.push(std::mem::take(&mut cur));
            cur_bytes = 0;
        }
        cur.extend(comps[ci].iter().map(|&slot| fn_item_indices[slot]));
        cur_bytes += sz;
    }
    if !cur.is_empty() {
        low_crates.push(cur);
    }
    for bucket in low_crates.iter_mut() {
        bucket.sort_unstable_by_key(|&idx| items[idx].start);
    }

    // ---- sets de items para emisión ------------------------------------------
    let movable_fns: std::collections::HashSet<usize> = comps
        .iter()
        .enumerate()
        .filter(|&(ci, _)| movable[ci])
        .flat_map(|(_, comp)| comp.iter().map(|&slot| fn_item_indices[slot]))
        .collect();
    let bin_set: std::collections::HashSet<usize> = bin_item_indices.iter().copied().collect();
    let mut base_items: Vec<usize> = (0..items.len())
        .filter(|&i| {
            matches!(items[i].kind, Kind::Const | Kind::Static | Kind::Struct | Kind::Enum | Kind::Trait | Kind::MacroRules | Kind::Impl | Kind::ThreadLocal)
                || movable_fns.contains(&i)
        })
        .collect();
    base_items.sort_unstable_by_key(|&i| items[i].start);

    // ---- emitir fuentes ------------------------------------------------------
    let mut files: Vec<(String, String)> = Vec::new();
    let low_names: Vec<String> = (1..=low_crates.len()).map(|n| format!("layer1_{n}")).collect();

    // base (data + impls + thread_locals + cierre fijo de fns)
    {
        let mut body: Vec<String> = Vec::new();
        for &idx in &base_items {
            if items[idx].kind == Kind::ThreadLocal {
                body.extend(emit_thread_local(&lines, &items[idx]));
                body.push(String::new());
                continue;
            }
            body.extend(emit_item(&lines, &items[idx], &shadow, true));
            body.push(String::new());
        }
        let mut src = String::with_capacity(2 << 20);
        src.push_str(ALLOW);
        src.push_str(&body.join("\n"));
        files.push(("base/src/lib.rs".to_string(), src));
    }

    // low crates
    for (k, name) in low_names.iter().enumerate() {
        let mut body: Vec<String> = vec!["use base::*;".to_string()];
        for prev in &low_names[..k] {
            body.push(format!("use {prev}::*;"));
        }
        for &idx in &low_crates[k] {
            if movable_fns.contains(&idx) || bin_set.contains(&idx) {
                continue; // no deberían estar aquí (packing los excluye)
            }
            body.extend(emit_item(&lines, &items[idx], &shadow, false));
            body.push(String::new());
        }
        let mut src = String::with_capacity(2 << 20);
        src.push_str(ALLOW);
        src.push_str(&body.join("\n"));
        files.push((format!("{name}/src/lib.rs"), src));
    }

    // bin
    {
        let mut body: Vec<String> = vec![
            "#![allow(dead_code,unused_variables,unused_mut)]".to_string(),
            "use base::*;".to_string(),
        ];
        for name in &low_names {
            body.push(format!("use {name}::*;"));
        }
        body.push(String::new());
        for &idx in &bin_item_indices {
            for j in items[idx].start..items[idx].end {
                if shadow[j] {
                    continue;
                }
                body.push(lines[j].to_string());
            }
            body.push(String::new());
        }
        files.push(("bin/src/main.rs".to_string(), body.join("\n")));
    }

    // ---- workspace + manifests ------------------------------------------------
    let mut members: Vec<String> = vec!["base".to_string()];
    members.extend(low_names.iter().cloned());
    members.push("bin".to_string());
    let mut ws = String::with_capacity(1024);
    ws.push_str("[workspace]\nresolver = \"2\"\nmembers = [\n");
    for m in &members {
        ws.push_str(&format!("    \"{m}\",\n"));
    }
    ws.push_str("]\n\n[workspace.dependencies]\nflate2 = { version = \"=1.0.35\", default-features = false, features = [\"rust_backend\"] }\n\n[profile.release]\npanic = \"unwind\"\nstrip = \"symbols\"\n\n[profile.dev]\ndebug = false\nincremental = false\n");
    files.push(("Cargo.toml".to_string(), ws));

    for m in &members {
        let bin = m == "bin";
        let mut toml = format!("[package]\nname = \"{m}\"\nversion = \"0.0.0\"\nedition = \"2021\"\n");
        if bin {
            toml.push_str("\n[[bin]]\nname = \"mc_aot_generated\"\npath = \"src/main.rs\"\n");
        }
        toml.push_str("\n[dependencies]\n");
        if m != "base" {
            toml.push_str("base = { path = \"../base\" }\n");
            for (j, prev) in low_names.iter().enumerate() {
                if prev == m {
                    continue;
                }
                if m == "bin" {
                    toml.push_str(&format!("{prev} = {{ path = \"../{prev}\" }}\n"));
                } else {
                    let k: usize = m["layer1_".len()..].parse().expect("índice layer1");
                    if j + 1 < k {
                        toml.push_str(&format!("{prev} = {{ path = \"../{prev}\" }}\n"));
                    }
                }
            }
        }
        toml.push_str("flate2.workspace = true\n");
        files.push((format!("{m}/Cargo.toml"), toml));
    }

    Ok(Partition { files })
}

/// Punto de entrada público: devuelve (ruta_relativa, contenido).
pub fn split_crate(source: &str) -> Result<Vec<(String, String)>, String> {
    let partition = partition(source)?;
    Ok(partition.files)
}
