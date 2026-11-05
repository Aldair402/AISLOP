//! Prototipo aislado: eventos SLF4J limitados sobre un FileAppender real log4rs.
//! No implementa configuración Log4j/Minecraft ni está conectado al traductor.
use std::{path::Path, sync::{Arc, Mutex}};
use log::{Level, LevelFilter, Log, Metadata, Record};
use log4rs::{append::file::FileAppender, config::{Appender, Config, Root}, encode::{Encode, Write}};

#[derive(Debug)]
struct HexEventEncoder;
fn hex(s: &str) -> String { s.as_bytes().iter().map(|b| format!("{b:02x}")).collect() }
impl Encode for HexEventEncoder {
    fn encode(&self, w: &mut dyn Write, record: &Record<'_>) -> anyhow::Result<()> {
        writeln!(w, "{}|{}|{}", record.level(), hex(record.target()), hex(&record.args().to_string()))?;
        Ok(())
    }
}
/// Sólo sustituye marcadores `{}` sin barras invertidas; los argumentos son String o null.
/// Otras formas de SLF4J (objetos, Throwable, marcadores, escapes) deben ser rechazadas.
pub fn format_string_args(template: &str, args: &[Option<&str>]) -> Result<String, &'static str> {
    if template.contains('\\') { return Err("escapes SLF4J no implementados"); }
    if args.is_empty() { return Ok(template.to_owned()); }
    let mut out=String::new(); let mut rest=template;
    for arg in args {
        if let Some(i)=rest.find("{}") {
            out.push_str(&rest[..i]); out.push_str(arg.unwrap_or("null")); rest=&rest[i+2..];
        } else { break; }
    }
    out.push_str(rest); Ok(out)
}
/// Vista inmutable y acotada de los padres de un marker; no modela su identidad ni mutaciones.
#[derive(Debug)]
pub struct Marker<'a> { pub name: &'a str, pub parents: &'a [Marker<'a>] }
fn is_network_marker(marker: &Marker<'_>) -> Result<bool,String> {
    let mut todo=vec![marker];let mut visited=0usize;
    while let Some(node)=todo.pop(){
        visited+=1;if visited>10000{return Err("grafo de markers excede el perfil acotado".into());}
        if node.name=="NETWORK_PACKETS" {return Ok(true);}
        todo.extend(node.parents.iter());
    }
    Ok(false)
}
/// Sink de prueba real en archivo (no stdout, rotación, XML ni logger de Minecraft).
pub struct EventSink { logger: log4rs::Logger, errors: Arc<Mutex<Vec<String>>>, operation: Mutex<()> }
impl EventSink {
    pub fn new(path: &Path, root: LevelFilter) -> Result<Self,String> {
        let text=path.to_str().ok_or("ruta no UTF-8 no implementada")?;
        if text.contains("$ENV{") || text.contains("$TIME{") {return Err("expansión de ruta log4rs no permitida".into());}
        let file=FileAppender::builder().append(true).encoder(Box::new(HexEventEncoder)).build(path).map_err(|e|e.to_string())?;
        let config=Config::builder().appender(Appender::builder().build("file",Box::new(file))).build(Root::builder().appender("file").build(root)).map_err(|e|e.to_string())?;
        let errors=Arc::new(Mutex::new(Vec::new()));let errors_for_handler=errors.clone();
        let logger=log4rs::Logger::new_with_err_handler(config,Box::new(move |e|errors_for_handler.lock().unwrap().push(e.to_string())));
        Ok(Self{logger,errors,operation:Mutex::new(())})
    }
    pub fn enabled(&self, level: Level, name: &str) -> bool {
        self.logger.enabled(&Metadata::builder().level(level).target(name).build())
    }
    pub fn emit(&self, level: Level, name: &str, template: &str, args: &[Option<&str>]) -> Result<(),String> {
        let _operation=self.operation.lock().map_err(|e|e.to_string())?;
        let msg=format_string_args(template,args)?;
        let fmt=format_args!("{msg}");
        let record=Record::builder().level(level).target(name).args(fmt).build();
        self.logger.log(&record);
        let mut errors=self.errors.lock().map_err(|e|e.to_string())?;
        if !errors.is_empty() { return Err(errors.remove(0)); } Ok(())
    }
    /// Filtro raíz del XML oficial: rechaza NETWORK_PACKETS y marcadores que lo heredan.
    /// La consulta enabled sin marker sigue dependiendo sólo del nivel, como el oráculo probado.
    pub fn emit_minecraft_root(&self, level:Level, name:&str, marker:Option<&Marker<'_>>, template:&str, args:&[Option<&str>])->Result<(),String>{
        if let Some(m)=marker { if is_network_marker(m)? {return Ok(());} }
        self.emit(level,name,template,args)
    }
    /// log4rs FileAppender ya hace flush en append; flush() de la fachada no devuelve errores.
    pub fn flush(&self) { self.logger.flush(); }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize,Ordering};
    static N:AtomicUsize=AtomicUsize::new(0);
    fn path()->std::path::PathBuf{std::env::temp_dir().join(format!("mc-log4rs-test-{}-{}",std::process::id(),N.fetch_add(1,Ordering::Relaxed)))}
    #[test] fn formatting_and_guard(){
        assert_eq!(format_string_args("{} / {} / {}",&[Some("世界"),None]).unwrap(),"世界 / null / {}");
        assert_eq!(format_string_args("{}",&[]).unwrap(),"{}");
        assert!(format_string_args(r"\{}",&[Some("x")]).is_err());
    }
    #[test] fn append_and_filter(){
        let p=path();std::fs::write(&p,b"previous\n").unwrap();
        let s=EventSink::new(&p,LevelFilter::Info).unwrap();
        assert!(s.enabled(Level::Info,"x"));assert!(!s.enabled(Level::Debug,"x"));
        s.emit(Level::Info,"x","{}",&[Some("hello")]).unwrap();
        s.emit(Level::Debug,"x","hidden",&[]).unwrap();s.flush();drop(s);
        assert_eq!(std::fs::read_to_string(&p).unwrap(),"previous\nINFO|78|68656c6c6f\n");std::fs::remove_file(p).unwrap();
    }
    #[test] fn reject_path_interpolation(){
        assert!(EventSink::new(Path::new("$ENV{HOME}/oops"),LevelFilter::Info).is_err());
        assert!(EventSink::new(Path::new("$TIME{%Y}/oops"),LevelFilter::Info).is_err());
    }
    #[test] fn concurrent_records_are_complete(){
        let p=path();let sink=std::sync::Arc::new(EventSink::new(&p,LevelFilter::Info).unwrap());
        let mut workers=vec![];
        for w in 0..8 {let sink=sink.clone();workers.push(std::thread::spawn(move||{
            for i in 0..250 {let value=format!("{w}:{i}");sink.emit(Level::Info,"worker","{}",&[Some(&value)]).unwrap();}
        }));}
        for worker in workers {worker.join().unwrap();}sink.flush();drop(sink);
        let data=std::fs::read_to_string(&p).unwrap();let lines=data.lines().collect::<std::collections::HashSet<_>>();
        assert_eq!(lines.len(),2000);assert_eq!(data.lines().count(),2000);
        for w in 0..8 {for i in 0..250 {let event=format!("INFO|{}|{}",hex("worker"),hex(&format!("{w}:{i}")));assert!(lines.contains(event.as_str()));}}
        std::fs::remove_file(p).unwrap();
    }
    #[cfg(target_os="linux")]
    #[test] fn write_error_is_not_silenced(){
        if !Path::new("/dev/full").exists(){return;}
        let sink=EventSink::new(Path::new("/dev/full"),LevelFilter::Info).unwrap();
        assert!(sink.emit(Level::Info,"x","x",&[]).is_err());
    }
}
