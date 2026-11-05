//! Ejecuta fixture diferencial; no es un servidor.
use log::{Level,LevelFilter};
use mc_log4rs_prototype::{EventSink,Marker,format_string_args};
fn main()->Result<(),Box<dyn std::error::Error>>{
 let argv:Vec<_>=std::env::args().collect();
 if argv.len()!=3{return Err("uso: fixture <archivo> <OFF|ERROR|WARN|INFO|DEBUG|TRACE>".into());}
 if argv[2]=="MARKER_EVENT" {
  let sink=EventSink::new(argv[1].as_ref(),LevelFilter::Info)?;
  let blocked=Marker{name:"NETWORK_PACKETS",parents:&[]};
  let ancestors=[Marker{name:"NETWORK_PACKETS",parents:&[]}];
  let child=Marker{name:"INHERITS_NETWORK",parents:&ancestors};
  let allowed=Marker{name:"OTHER",parents:&[]};let name="net.minecraft.test.MarkerProbe";
  eprintln!("enabled|{}|{}|{}",sink.enabled(Level::Info,name),sink.enabled(Level::Info,name),sink.enabled(Level::Info,name));
  sink.emit_minecraft_root(Level::Debug,name,None,"disabled-debug",&[])?;
  sink.emit_minecraft_root(Level::Info,name,None,"unmarked",&[])?;
  sink.emit_minecraft_root(Level::Info,name,Some(&blocked),"blocked",&[])?;
  sink.emit_minecraft_root(Level::Info,name,Some(&child),"blocked-child",&[])?;
  sink.emit_minecraft_root(Level::Info,name,Some(&allowed),"allowed",&[])?;
  sink.emit_minecraft_root(Level::Warn,name,None,"warning",&[])?;return Ok(());
 }
 if argv[2]=="EULA_EVENT" {
  // Sólo emite una entrada de fixture: NO implementa ni ejecuta Eula.
  let sink=EventSink::new(argv[1].as_ref(),LevelFilter::Info)?;
  sink.emit(Level::Warn,"net.minecraft.server.Eula","Failed to load {}",&[Some("eula.txt")])?;
  return Ok(());
 }
 let filter:LevelFilter=argv[2].parse()?;
 let sink=EventSink::new(argv[1].as_ref(),filter)?;
 let levels=[Level::Error,Level::Warn,Level::Info,Level::Debug,Level::Trace];
 let names=["server","net.minecraft.server.Main","玩家.世界",""];
 let patterns=["Server starting","hello {}","{}|{}","none {} {} {}","こんにちは {}","","{}{}{}"];
 let arguments:Vec<Vec<Option<&str>>>=vec![vec![],vec![Some("Alex")],vec![Some("a"),None],vec![Some("世界"),Some("x"),Some("extra")]];
 for l in levels { for name in names { println!("enabled|{l}|{}|{}",name,sink.enabled(l,name)); for pat in patterns { for args in &arguments {sink.emit(l,name,pat,args)?;} } } }
 if format_string_args("\\{}", &[Some("x")]).is_ok(){return Err("guarda de escape falló".into());}
 sink.flush(); Ok(())
}
