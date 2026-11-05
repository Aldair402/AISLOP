// Experimento interno: referencias entre objetos numéricos registrados en un
// SharedHeap. Layouts facilitados por el harness DESPUÉS de verificar classfiles.
// No hay registro automático, GC, subtipos, arrays, String ni clases compartidas.
#[derive(Clone,Copy,PartialEq,Eq)] enum NumericGraphSlot { Int, Ref(&'static str) }
struct NumericGraphLayout { class:&'static str, fields:&'static [NumericGraphSlot] }
#[derive(Default)] struct NumericGraphMap {
    forward:std::collections::HashMap<usize,(concurrent_heap::ObjectId,&'static NumericGraphLayout)>,
    backward:std::collections::HashMap<concurrent_heap::ObjectId,(usize,&'static str)>,
}
struct NumericGraphState {owner:std::sync::Arc<()>, map:std::sync::Mutex<NumericGraphMap>}
struct NumericGraphBridge {shared:concurrent_heap::SharedHeap,state:std::sync::Arc<NumericGraphState>}
struct NumericGraphObject { class:&'static str, handle:NumericObjectHandle, layout:&'static NumericGraphLayout, state:std::sync::Weak<NumericGraphState>, domain:usize }
impl concurrent_heap::ExternalObject for NumericGraphObject {
    fn identity_key(&self)->usize {std::sync::Arc::as_ptr(&self.handle.fields) as usize}
    fn domain_key(&self)->usize {self.domain}
    fn class(&self)->&'static str {self.class}
    fn field_count(&self)->Result<usize,&'static str> {
        let fields=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;
        if fields.len()!=self.layout.fields.len() || fields.iter().zip(self.layout.fields).any(|(v,k)|!matches!((v,k),(V::I(_),NumericGraphSlot::Int)|(V::R(_),NumericGraphSlot::Ref(_)))) {return Err("grafo: layout incompatible");}
        Ok(fields.len())
    }
    fn read(&self,slot:usize)->Result<concurrent_heap::ExternalValue,&'static str> {
        let state=self.state.upgrade().ok_or("grafo: sesión cerrada")?;
        let kind=*self.layout.fields.get(slot).ok_or("campo inexistente")?;
        let value={let fields=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;*fields.get(slot).ok_or("campo inexistente")?};
        match (kind,value) {
            (NumericGraphSlot::Int,V::I(v))=>Ok(concurrent_heap::ExternalValue::Int(v)),
            (NumericGraphSlot::Ref(_),V::R(None))=>Ok(concurrent_heap::ExternalValue::Ref(None)),
            (NumericGraphSlot::Ref(expected),V::R(Some(id)))=>{
                let map=state.map.lock().map_err(|_|"grafo: mapa dañado")?;
                match map.forward.get(&id){Some((target,layout)) if layout.class==expected=>Ok(concurrent_heap::ExternalValue::Ref(Some(*target))),_=>Err("grafo: destino no registrado o incompatible")}
            }
            _=>Err("grafo: tipo de campo incompatible")
        }
    }
    fn write(&self,slot:usize,value:concurrent_heap::ExternalValue)->Result<(),&'static str> {
        let _state=self.state.upgrade().ok_or("grafo: sesión cerrada")?;
        let kind=*self.layout.fields.get(slot).ok_or("campo inexistente")?;
        let value=match (kind,value) {
            (NumericGraphSlot::Int,concurrent_heap::ExternalValue::Int(v))=>V::I(v),
            (NumericGraphSlot::Ref(_),_)=>return Err("grafo: escritura de referencia no soportada"),
            _=>return Err("grafo: tipo de campo incompatible")
        };
        let mut fields=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;
        let field=fields.get_mut(slot).ok_or("campo inexistente")?;
        if std::mem::discriminant(field)!=std::mem::discriminant(&value){return Err("grafo: tipo de campo incompatible");}*field=value;Ok(())
    }
    fn enter(&self)->Result<Box<dyn concurrent_heap::ExternalGuard>,&'static str> {let _state=self.state.upgrade().ok_or("grafo: sesión cerrada")?;Ok(Box::new(self.handle.enter_monitor()?))}
}
impl NumericGraphBridge {
    fn new(owner:&Heap,shared:&concurrent_heap::SharedHeap)->Self {Self {shared:shared.clone(),state:std::sync::Arc::new(NumericGraphState{owner:owner.bridge_owner.clone(),map:std::sync::Mutex::new(NumericGraphMap::default())})}}
    fn attach(&self,owner:&mut Heap,id:usize,layout:&'static NumericGraphLayout)->Result<concurrent_heap::ObjectId,&'static str> {
        if !std::sync::Arc::ptr_eq(&owner.bridge_owner,&self.state.owner) {return Err("grafo: otro heap numérico");}
        fn valid(fields:&[V],layout:&NumericGraphLayout)->bool {fields.len()==layout.fields.len() && fields.iter().zip(layout.fields).all(|(v,k)|matches!((v,k),(V::I(_),NumericGraphSlot::Int)|(V::R(_),NumericGraphSlot::Ref(_))))}
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
}
