// Experimento interno: referencias entre objetos numéricos registrados en un
// SharedHeap. Layouts facilitados por el harness DESPUÉS de verificar classfiles.
// No hay registro automático, GC, subtipos, arrays, String ni clases compartidas.
// Ref: campo final, solo lectura. MutRef: campo no final, escribible desde el
// backend concurrente bajo el mutex de campos; el destino debe estar publicado.
#[derive(Clone,Copy,PartialEq,Eq)] enum NumericGraphSlot { Int, Ref(&'static str), MutRef(&'static str) }
#[derive(Clone,Copy)] struct NumericGraphLayout { class:&'static str, fields:&'static [NumericGraphSlot] }
// La etiqueta interna V::I cubre int/byte/char/short/boolean: el layout debe
// venir de un classfile verificado, no de la variante del heap.
fn graph_layout_matches(fields:&[V],layout:&NumericGraphLayout)->bool {
    fields.len()==layout.fields.len() && fields.iter().zip(layout.fields).all(|(v,k)|matches!((v,k),(V::I(_),NumericGraphSlot::Int)|(V::R(_),NumericGraphSlot::Ref(_))|(V::R(_),NumericGraphSlot::MutRef(_))))
}
#[derive(Default)] struct NumericGraphMap {
    forward:std::collections::HashMap<usize,(concurrent_heap::ObjectId,&'static NumericGraphLayout)>,
    backward:std::collections::HashMap<concurrent_heap::ObjectId,(usize,&'static str)>,
}
struct NumericGraphState {owner:std::sync::Arc<()>, map:std::sync::Mutex<NumericGraphMap>}
struct NumericGraphBridge {shared:concurrent_heap::SharedHeap,state:std::sync::Arc<NumericGraphState>,session:Option<PublishSessionGuard>}
struct NumericGraphObject { class:&'static str, handle:NumericObjectHandle, layout:&'static NumericGraphLayout, state:std::sync::Weak<NumericGraphState>, domain:usize }
impl concurrent_heap::ExternalObject for NumericGraphObject {
    fn identity_key(&self)->usize {std::sync::Arc::as_ptr(&self.handle.fields) as usize}
    fn domain_key(&self)->usize {self.domain}
    fn class(&self)->&'static str {self.class}
    fn field_count(&self)->Result<usize,&'static str> {
        let fields=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;
        if !graph_layout_matches(&fields,self.layout) {return Err("grafo: layout incompatible");}
        Ok(fields.len())
    }
    fn read(&self,slot:usize)->Result<concurrent_heap::ExternalValue,&'static str> {
        let state=self.state.upgrade().ok_or("grafo: sesión cerrada")?;
        let kind=*self.layout.fields.get(slot).ok_or("campo inexistente")?;
        let value={let fields=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;*fields.get(slot).ok_or("campo inexistente")?};
        match (kind,value) {
            (NumericGraphSlot::Int,V::I(v))=>Ok(concurrent_heap::ExternalValue::Int(v)),
            (NumericGraphSlot::Ref(_),V::R(None))|(NumericGraphSlot::MutRef(_),V::R(None))=>Ok(concurrent_heap::ExternalValue::Ref(None)),
            (NumericGraphSlot::Ref(expected),V::R(Some(id)))|(NumericGraphSlot::MutRef(expected),V::R(Some(id)))=>{
                let map=state.map.lock().map_err(|_|"grafo: mapa dañado")?;
                match map.forward.get(&id){Some((target,layout)) if layout.class==expected=>Ok(concurrent_heap::ExternalValue::Ref(Some(*target))),_=>Err("grafo: destino no registrado o incompatible")}
            }
            _=>Err("grafo: tipo de campo incompatible")
        }
    }
    fn write(&self,slot:usize,value:concurrent_heap::ExternalValue)->Result<(),&'static str> {
        let alive=self.state.upgrade().ok_or("grafo: sesión cerrada")?;
        let kind=*self.layout.fields.get(slot).ok_or("campo inexistente")?;
        let value=match (kind,value) {
            (NumericGraphSlot::Int,concurrent_heap::ExternalValue::Int(v))=>V::I(v),
            (NumericGraphSlot::Ref(_),_)=>return Err("grafo: escritura de referencia no soportada"),
            (NumericGraphSlot::MutRef(_),concurrent_heap::ExternalValue::Ref(None))=>V::R(None),
            (NumericGraphSlot::MutRef(expected),concurrent_heap::ExternalValue::Ref(Some(target)))=>{
                // Solo destinos ya publicados en esta sesión y de la clase esperada.
                let map=alive.map.lock().map_err(|_|"grafo: mapa dañado")?;
                match map.backward.get(&target){Some((index,c)) if *c==expected=>V::R(Some(*index)),_=>return Err("grafo: destino no registrado o incompatible")}
            }
            _=>return Err("grafo: tipo de campo incompatible")
        };
        let mut fields=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;
        let field=fields.get_mut(slot).ok_or("campo inexistente")?;
        if std::mem::discriminant(field)!=std::mem::discriminant(&value){return Err("grafo: tipo de campo incompatible");}*field=value;Ok(())
    }
    fn enter(&self)->Result<Box<dyn concurrent_heap::ExternalGuard>,&'static str> {let _state=self.state.upgrade().ok_or("grafo: sesión cerrada")?;Ok(Box::new(self.handle.enter_monitor()?))}
}
impl NumericGraphBridge {
    fn new(owner:&Heap,shared:&concurrent_heap::SharedHeap)->Self {Self {shared:shared.clone(),state:std::sync::Arc::new(NumericGraphState{owner:owner.bridge_owner.clone(),map:std::sync::Mutex::new(NumericGraphMap::default())}),session:None}}
    fn attach(&self,owner:&mut Heap,id:usize,layout:&'static NumericGraphLayout)->Result<concurrent_heap::ObjectId,&'static str> {
        if !std::sync::Arc::ptr_eq(&owner.bridge_owner,&self.state.owner) {return Err("grafo: otro heap numérico");}
        fn valid(fields:&[V],layout:&NumericGraphLayout)->bool {graph_layout_matches(fields,layout)}
        let class=match owner.arrays.get(id){
            Some(Array::Obj(c,fields))=>{if !valid(fields,layout){return Err("grafo: layout incompatible");}*c},
            Some(Array::SharedObj(c,handle))=>{let fields=handle.fields.lock().map_err(|_|"objeto compartido dañado")?;if !valid(&fields,layout){return Err("grafo: layout incompatible");}*c},
            Some(_)=>return Err("grafo: solo objetos ordinarios"),None=>return Err("referencia inválida")
        };
        if class!=layout.class || !class.starts_with("net/minecraft/") {return Err("grafo: clase incompatible");}
        {let map=self.state.map.lock().map_err(|_|"grafo: mapa dañado")?;if let Some((_,old))=map.forward.get(&id){if old.class!=layout.class || old.fields!=layout.fields{return Err("grafo: layout inconsistente");}}}
        let handle=share_project_object(owner,id)?;
        let object=NumericGraphObject{class,handle,layout,state:std::sync::Arc::downgrade(&self.state),domain:std::sync::Arc::as_ptr(&self.state) as usize};
        let target=self.shared.attach_external(std::sync::Arc::new(object))?;
        let mut map=self.state.map.lock().map_err(|_|"grafo: mapa dañado")?;
        if let Some((prior,old))=map.forward.get(&id){if *prior!=target || old.class!=class || old.fields!=layout.fields{return Err("grafo: identidad inconsistente");}}
        if let Some((prior,c))=map.backward.get(&target){if *prior!=id || *c!=class{return Err("grafo: identidad inconsistente");}}
        map.forward.insert(id,(target,layout));map.backward.insert(target,(id,class));Ok(target)
    }

    // A-03: instala la sesión de publicación automática. A partir de aquí, todo
    // objeto admitido que cree el bytecode numérico se comparte al construirse;
    // el harness no enumera instancias ni pasa layouts por objeto.
    fn install(owner:&Heap,shared:&concurrent_heap::SharedHeap,layouts:&'static [NumericGraphLayout])->Result<Self,&'static str> {
        let mut bridge=Self::new(owner,shared);
        let sink=NumericGraphSink{shared:shared.clone(),layouts,state:bridge.state.clone()};
        bridge.session=Some(install_publish_session(owner,std::sync::Arc::new(sink))?);
        Ok(bridge)
    }
    fn lookup(&self,id:usize)->Result<concurrent_heap::ObjectId,&'static str> {
        let map=self.state.map.lock().map_err(|_|"grafo: mapa dañado")?;
        map.forward.get(&id).map(|(target,_)|*target).ok_or("grafo: objeto no publicado")
    }
}
struct NumericGraphSink { shared:concurrent_heap::SharedHeap, layouts:&'static [NumericGraphLayout], state:std::sync::Arc<NumericGraphState> }
impl PublishSink for NumericGraphSink {
    fn admits(&self,class:&'static str)->bool {self.layouts.iter().any(|layout|layout.class==class)}
    fn publish(&self,owner:usize,index:usize,class:&'static str,handle:&NumericObjectHandle)->Result<(),&'static str> {
        let layout=self.layouts.iter().find(|layout|layout.class==class).ok_or("grafo: clase sin layout")?;
        {let fields=handle.fields.lock().map_err(|_|"objeto compartido dañado")?;if !graph_layout_matches(&fields,layout){return Err("grafo: layout incompatible");}}
        let object=NumericGraphObject{class,handle:handle.clone(),layout,state:std::sync::Arc::downgrade(&self.state),domain:owner};
        let target=self.shared.attach_external(std::sync::Arc::new(object))?;
        let mut map=self.state.map.lock().map_err(|_|"grafo: mapa dañado")?;
        if let Some((prior,old))=map.forward.get(&index) {if *prior!=target || old.class!=class {return Err("grafo: identidad inconsistente");}}
        if let Some((prior,c))=map.backward.get(&target) {if *prior!=index || *c!=class {return Err("grafo: identidad inconsistente");}}
        map.forward.insert(index,(target,layout));map.backward.insert(target,(index,class));Ok(())
    }
}
