// Puente INTERNO experimental entre un objeto del heap numérico y SharedHeap.
// Solo objetos ordinarios de proyecto cuyas ranuras son todas int. La clase
// debe proceder del Heap propietario. El layout lo proporciona un código interno
// de prueba después de verificar el classfile: solo clase final directa de Object,
// con todos sus campos de instancia de descriptor I en orden declarado.
// Las etiquetas V::I solas NO distinguen int de byte/char/short/boolean.
// No copia los campos ni transporta referencias, arrays, estáticos o excepciones.
struct NumericBridgeLayout {class:&'static str,int_fields:usize}
struct NumericExternalObject {
    class: &'static str,
    handle: NumericObjectHandle,
}
impl concurrent_heap::ExternalObject for NumericExternalObject {
    fn identity_key(&self)->usize {std::sync::Arc::as_ptr(&self.handle.fields) as usize}
    fn domain_key(&self)->usize {std::sync::Arc::as_ptr(&self.handle.fields) as usize}
    fn class(&self)->&'static str {self.class}
    fn field_count(&self)->Result<usize,&'static str> {
        let f=self.handle.fields.lock().map_err(|_|"objeto compartido dañado")?;
        if f.iter().any(|v|!matches!(v,V::I(_))) {return Err("puente: solo campos int");}
        Ok(f.len())
    }
    fn read(&self,field:usize)->Result<concurrent_heap::ExternalValue,&'static str> {self.handle.read_int(field).map(concurrent_heap::ExternalValue::Int)}
    fn write(&self,field:usize,value:concurrent_heap::ExternalValue)->Result<(),&'static str> {match value{concurrent_heap::ExternalValue::Int(v)=>self.handle.write_int(field,v),_=>Err("puente: solo campos int")}}
    fn enter(&self)->Result<Box<dyn concurrent_heap::ExternalGuard>,&'static str> {
        Ok(Box::new(self.handle.enter_monitor()?))
    }
}
fn bridge_numeric_object(h:&mut Heap,shared:&concurrent_heap::SharedHeap,id:usize,layout:&NumericBridgeLayout)->Result<concurrent_heap::ObjectId,&'static str> {
    let class=match h.arrays.get(id) {
        Some(Array::Obj(class,fields))=>{
            if fields.len()!=layout.int_fields || fields.iter().any(|v|!matches!(v,V::I(_))) {return Err("puente: layout int incompatible");}
            *class
        }
        Some(Array::SharedObj(class,handle))=>{
            let fields=handle.fields.lock().map_err(|_|"objeto compartido dañado")?;
            if fields.len()!=layout.int_fields || fields.iter().any(|v|!matches!(v,V::I(_))) {return Err("puente: layout int incompatible");}
            *class
        }
        Some(_)=>return Err("puente: solo objetos de proyecto ordinarios"),
        None=>return Err("referencia inválida"),
    };
    if !class.starts_with("net/minecraft/") || class!=layout.class {return Err("puente: clase fuera del perfil");}
    let handle=share_project_object(h,id)?;
    shared.attach_external(std::sync::Arc::new(NumericExternalObject{class,handle}))
}
