//! Perfil AOT experimental de un Runnable cuyo único efecto es incrementar un
//! campo int de un objeto final bajo su monitor. No es un traductor general de
//! Runnable, ni conecta ForkJoinPool Java al backend principal.
use super::{class_from_jar, find_method_inner, metadata, method_ref, object, CpEntry, Result};
use std::path::Path;

pub(super) struct Plan {
    pub target_class: String,
    pub static_field: String,
    pub delta: i32,
    pub wrapper: WorkerWrapper,
}
#[derive(Clone,Copy)]
pub(super) enum WorkerWrapper { None, Util4, TickTask }

fn ix(b: &[u8], at: usize) -> u16 {
    u16::from_be_bytes([b[at], b[at + 1]])
}
fn only_method<'a>(meta: &'a metadata::Class, name: &str, desc: &str) -> Result<&'a metadata::Method> {
    let matching = meta.methods.iter().filter(|m| m.name == name && m.descriptor == desc).collect::<Vec<_>>();
    if matching.len() != 1 { return Err(format!("worker compartido: método ausente o duplicado: {name}{desc}")); }
    Ok(matching[0])
}
fn no_clinit(meta: &metadata::Class) -> Result<()> {
    if meta.methods.iter().any(|m| m.name == "<clinit>") {
        Err(format!("worker compartido: <clinit> no permitido: {}", meta.name))
    } else { Ok(()) }
}
fn ordinary_final(meta: &metadata::Class, name: &str) -> Result<()> {
    if meta.name != name || !name.starts_with("net/minecraft/") || meta.flags & 0x0010 == 0
        || meta.flags & (0x0200 | 0x0400 | 0x4000) != 0 || meta.parent.as_deref() != Some("java/lang/Object") {
        return Err(format!("worker compartido: clase final directa de Object requerida: {name}"));
    }
    Ok(())
}
fn expect_field<'a>(m: &'a super::Method, at: usize) -> Result<(&'a str, &'a str, &'a str)> {
    if !matches!(m.cp.get(ix(&m.code,at) as usize),Some(CpEntry::FieldRef(..))) {return Err("worker compartido: Fieldref inválido".into());}
    object::field_ref(&m.cp,ix(&m.code,at))
}
fn expect_method<'a>(m: &'a super::Method, at: usize) -> Result<(&'a str, &'a str, &'a str)> {
    if !matches!(m.cp.get(ix(&m.code,at) as usize),Some(CpEntry::MethodRef(..))) {return Err("worker compartido: Methodref inválido".into());}
    method_ref(&m.cp,ix(&m.code,at))
}
fn body(data: &[u8], name: &str, desc: &str, static_: bool, sync: bool) -> Result<super::Method> {
    let m=find_method_inner(data,name,desc,false,static_,true)?;
    if m.synchronized != sync {return Err(format!("worker compartido: synchronized incompatible: {name}"));}
    Ok(m)
}

/// Comprueba bytecode y miembros completos del perfil antes de generar un
/// ejecutable. El constructor de la tarea se comprueba, pero el objeto Runnable
/// no escapa ni se materializa en este experimento de scheduling controlado.
pub(super) fn verify(jar: &Path, root: &str, static_field: &str, task: &str, tick: &str, read: &str, wrapper: WorkerWrapper) -> Result<Plan> {
    match wrapper {WorkerWrapper::None=>(),WorkerWrapper::Util4=>verify_util_wrapper(jar)?,WorkerWrapper::TickTask=>verify_ticktask_wrapper(jar)?}
    let task_data=class_from_jar(jar,task)?;let tm=metadata::parse(&task_data)?;
    ordinary_final(&tm,task)?;no_clinit(&tm)?;
    if tm.interfaces.as_slice() != ["java/lang/Runnable"] {return Err("worker compartido: Runnable directo requerido".into());}
    let captures=tm.fields.iter().filter(|f|f.flags&8==0).collect::<Vec<_>>();
    if captures.len()!=1 || captures[0].flags&0x10==0 {return Err("worker compartido: captura final única requerida".into());}
    let capture=captures[0];let target=capture.descriptor.strip_prefix('L').and_then(|s|s.strip_suffix(';')).ok_or("worker compartido: captura no es objeto")?;
    let target_data=class_from_jar(jar,target)?;let target_meta=metadata::parse(&target_data)?;
    ordinary_final(&target_meta,target)?;no_clinit(&target_meta)?;
    if !target_meta.interfaces.is_empty() {return Err("worker compartido: interfaces del destino fuera de perfil".into());}
    let fields=target_meta.fields.iter().filter(|f|f.flags&8==0).collect::<Vec<_>>();
    if fields.len()!=1 || fields[0].descriptor!="I" || fields[0].flags&(0x0010|0x0040)!=0 {
        return Err("worker compartido: único campo int mutable no volatile requerido".into());
    }
    let value=fields[0];
    if tm.methods.iter().any(|m|m.name!="<init>" && m.name!="run") {return Err("worker compartido: métodos adicionales en Runnable fuera de perfil".into());}
    let run_meta=only_method(&tm,"run","()V")?;
    if run_meta.flags&1==0 || run_meta.flags&(8|0x20|0x100|0x400)!=0 {return Err("worker compartido: run público sin synchronized requerido".into());}
    let run=body(&task_data,"run","()V",false,false)?;let b=&run.code;
    if b.len()!=8 || b[0]!=0x2a || b[1]!=0xb4 || b[4]!=0xb6 || b[7]!=0xb1 {return Err("worker compartido: bytecode run fuera de perfil".into());}
    if expect_field(&run,2)?!=(task,capture.name.as_str(),capture.descriptor.as_str()){return Err("worker compartido: captura incorrecta".into());}
    let (owner,increment,desc)=expect_method(&run,5)?;
    if owner!=target || desc!="()V" {return Err("worker compartido: llamada de destino fuera de perfil".into());}
    let method=only_method(&target_meta,increment,desc)?;
    if target_meta.methods.iter().any(|m|m.name!="<init>" && (m.name!=increment || m.descriptor!=desc)) {return Err("worker compartido: métodos adicionales en destino fuera de perfil".into());}
    if method.flags&0x20==0 || method.flags&(8|2|0x100|0x400)!=0 {return Err("worker compartido: método synchronized de instancia requerido".into());}
    let inc=body(&target_data,increment,desc,false,true)?;let b=&inc.code;
    let delta=if b.len()==11 && b[0]==0x2a && b[1]==0x59 && b[2]==0xb4 && b[5]==0x04 && b[6]==0x60 && b[7]==0xb5 && b[10]==0xb1 {
        if expect_field(&inc,3)?!=(target,value.name.as_str(),"I") || expect_field(&inc,8)?!=(target,value.name.as_str(),"I") {return Err("worker compartido: campos de incremento incorrectos".into());}
        1
    } else if b.len()==14 && b[0]==0x2a && b[1]==0x59 && b[2]==0xb4 && b[5]==0x04 && b[6]==0xb8 && b[9]==0x60 && b[10]==0xb5 && b[13]==0xb1 {
        if expect_field(&inc,3)?!=(target,value.name.as_str(),"I") || expect_field(&inc,11)?!=(target,value.name.as_str(),"I") || expect_method(&inc,7)?!=("net/minecraft/core/QuartPos","toBlock","(I)I") {return Err("worker compartido: llamada QuartPos fuera de perfil".into());}
        // Equivalencia para el bytecode puro exacto, no para otras versiones ni
        // para argumentos arbitrarios. No se omite un inicializador de clase.
        let q=class_from_jar(jar,"net/minecraft/core/QuartPos")?;let qm=metadata::parse(&q)?;
        ordinary_final(&qm,"net/minecraft/core/QuartPos")?;no_clinit(&qm)?;
        if !qm.interfaces.is_empty() {return Err("worker compartido: interfaces QuartPos fuera de perfil".into());}
        let method=only_method(&qm,"toBlock","(I)I")?;
        if method.flags&0x0009!=0x0009 || method.flags&(0x20|0x100|0x400)!=0 {return Err("worker compartido: QuartPos.toBlock fuera de perfil".into());}
        let qbody=body(&q,"toBlock","(I)I",true,false)?;
        if qbody.code!=[0x1a,0x05,0x78,0xac] {return Err("worker compartido: bytecode QuartPos.toBlock fuera de perfil".into());}
        1_i32.wrapping_shl(2)
    } else {return Err("worker compartido: bytecode incremento fuera de perfil".into());};
    let ctor_desc=format!("(L{target};)V");only_method(&tm,"<init>",&ctor_desc)?;
    if tm.methods.iter().filter(|m|m.name=="<init>").count()!=1 {return Err("worker compartido: constructores adicionales fuera de perfil".into());}
    let ctor=body(&task_data,"<init>",&ctor_desc,false,false)?;let b=&ctor.code;
    if b.len()!=10 || b[0]!=0x2a || b[1]!=0xb7 || b[4]!=0x2a || b[5]!=0x2b || b[6]!=0xb5 || b[9]!=0xb1
       || expect_method(&ctor,2)?!=("java/lang/Object","<init>","()V") || expect_field(&ctor,7)?!=(task,capture.name.as_str(),capture.descriptor.as_str()) {
       return Err("worker compartido: constructor de captura no canónico".into());
    }
    let root_data=class_from_jar(jar,root)?;let rm=metadata::parse(&root_data)?;
    if rm.name!=root || !root.starts_with("net/minecraft/"){return Err("worker compartido: clase raíz fuera de perfil".into());}
    let root_fields=rm.fields.iter().filter(|f|f.name==static_field && f.descriptor==capture.descriptor && f.flags&8!=0).collect::<Vec<_>>();
    if root_fields.len()!=1 {return Err("worker compartido: campo static de destino ausente o ambiguo".into());}
    for name in [tick,read] {let m=only_method(&rm,name,"(I)I")?;if m.flags&8==0 || m.flags&(0x20|0x100|0x400)!=0 {return Err("worker compartido: método raíz debe ser static sin synchronized".into());}}
    let tick_m=body(&root_data,tick,"(I)I",true,false)?;let b=&tick_m.code;
    if b.len()!=8 || b[0]!=0xb2 || b[3]!=0xb6 || b[6]!=0x03 || b[7]!=0xac
        || expect_field(&tick_m,1)?!=(root,static_field,capture.descriptor.as_str()) || expect_method(&tick_m,4)?!=(target,increment,"()V") {
        return Err("worker compartido: tick fuera de perfil".into());
    }
    let read_m=body(&root_data,read,"(I)I",true,false)?;let b=&read_m.code;
    if b.len()!=7 || b[0]!=0xb2 || b[3]!=0xb4 || b[6]!=0xac
        || expect_field(&read_m,1)?!=(root,static_field,capture.descriptor.as_str()) || expect_field(&read_m,4)?!=(target,value.name.as_str(),"I") {
        return Err("worker compartido: lectura fuera de perfil".into());
    }
    Ok(Plan {target_class:target.to_owned(),static_field:static_field.to_owned(),delta,wrapper})
}

/// Reconoce SOLO el `Util$4` oficial. Se traduce únicamente su `run()` de
/// reenvío a la tarea ya verificada; no se materializa el wrapper ni toString.
fn verify_util_wrapper(jar:&Path)->Result<()> {
    let data=class_from_jar(jar,"net/minecraft/util/Util$4")?;
    pinned_hash(&data,"f822c28cdfe2a159614c595a78daddf9236b8772fe01e40d18d7d9cb92651390","Util$4")?;
    let m=metadata::parse(&data)?;
    if m.name!="net/minecraft/util/Util$4" || m.parent.as_deref()!=Some("java/lang/Object") || m.interfaces.as_slice()!=["java/lang/Runnable"] {return Err("worker compartido: Util$4 clase fuera de perfil".into());}
    no_clinit(&m)?;
    let run=only_method(&m,"run","()V")?;if run.flags&1==0 || run.flags&(8|0x20|0x100|0x400)!=0{return Err("worker compartido: Util$4.run fuera de perfil".into());}
    let r=body(&data,"run","()V",false,false)?;let b=&r.code;
    if b.len()!=10 || b[0]!=0x2a || b[1]!=0xb4 || b[4]!=0xb9 || b[7]!=1 || b[8]!=0 || b[9]!=0xb1
        || expect_field(&r,2)?!=("net/minecraft/util/Util$4","val$task","Ljava/lang/Runnable;")
        || !matches!(r.cp.get(ix(b,5) as usize),Some(CpEntry::InterfaceMethodRef(..)))
        || method_ref(&r.cp,ix(b,5))?!=("java/lang/Runnable","run","()V") {return Err("worker compartido: Util$4.run bytecode fuera de perfil".into());}
    let desc="(Ljava/lang/Runnable;Ljava/lang/String;)V";only_method(&m,"<init>",desc)?;let c=body(&data,"<init>",desc,false,false)?;let b=&c.code;
    if b.len()!=15 || b[0]!=0x2a || b[1]!=0x2b || b[2]!=0xb5 || b[5]!=0x2a || b[6]!=0x2c || b[7]!=0xb5 || b[10]!=0x2a || b[11]!=0xb7 || b[14]!=0xb1
      || expect_field(&c,3)?!=("net/minecraft/util/Util$4","val$task","Ljava/lang/Runnable;")
      || expect_field(&c,8)?!=("net/minecraft/util/Util$4","val$name","Ljava/lang/String;")
      || expect_method(&c,12)?!=("java/lang/Object","<init>","()V") {return Err("worker compartido: Util$4 constructor fuera de perfil".into());}
    Ok(())
}

fn pinned_hash(data:&[u8],expected:&str,name:&str)->Result<()> {
    use std::io::Write;
    let mut hash=std::process::Command::new("sha256sum").stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).spawn().map_err(|e|e.to_string())?;
    hash.stdin.take().ok_or("worker compartido: sin stdin sha256sum")?.write_all(data).map_err(|e|e.to_string())?;
    let digest=hash.wait_with_output().map_err(|e|e.to_string())?;
    if !digest.status.success() || String::from_utf8_lossy(&digest.stdout).split_whitespace().next()!=Some(expected) {return Err(format!("worker compartido: {name} versión no verificada"));}
    Ok(())
}
/// TickTask exacta: solo run con destino no nulo; no tick, cola ni despacho dinámico.
fn verify_ticktask_wrapper(jar:&Path)->Result<()> {
    let name="net/minecraft/server/TickTask";let data=class_from_jar(jar,name)?;
    pinned_hash(&data,"dae918ab7da617b85384411773b9759ffbc0c0609bfc06c7dc4af85b76fa69b6","TickTask")?;
    let m=metadata::parse(&data)?;
    if m.name!=name || m.parent.as_deref()!=Some("java/lang/Object") || m.interfaces.as_slice()!=["java/lang/Runnable"] {return Err("worker compartido: TickTask clase fuera de perfil".into());}
    no_clinit(&m)?;
    let run=only_method(&m,"run","()V")?;if run.flags&1==0 || run.flags&(8|0x20|0x100|0x400)!=0{return Err("worker compartido: TickTask.run fuera de perfil".into());}
    let r=body(&data,"run","()V",false,false)?;let b=&r.code;
    if b.len()!=10 || b[0]!=0x2a || b[1]!=0xb4 || b[4]!=0xb9 || b[7]!=1 || b[8]!=0 || b[9]!=0xb1
        || expect_field(&r,2)?!=(name,"runnable","Ljava/lang/Runnable;")
        || !matches!(r.cp.get(ix(b,5) as usize),Some(CpEntry::InterfaceMethodRef(..)))
        || method_ref(&r.cp,ix(b,5))?!=("java/lang/Runnable","run","()V") {return Err("worker compartido: TickTask.run bytecode fuera de perfil".into());}
    let desc="(ILjava/lang/Runnable;)V";only_method(&m,"<init>",desc)?;let c=body(&data,"<init>",desc,false,false)?;let b=&c.code;
    if b.len()!=15 || b[0]!=0x2a || b[1]!=0xb7 || b[4]!=0x2a || b[5]!=0x1b || b[6]!=0xb5 || b[9]!=0x2a || b[10]!=0x2c || b[11]!=0xb5 || b[14]!=0xb1
      || expect_method(&c,2)?!=("java/lang/Object","<init>","()V")
      || expect_field(&c,7)?!=(name,"tick","I") || expect_field(&c,12)?!=(name,"runnable","Ljava/lang/Runnable;") {return Err("worker compartido: TickTask constructor fuera de perfil".into());}
    Ok(())
}
