#!/usr/bin/env python3
"""Inventario estático de instrucciones; no estima compatibilidad ni ejecución real."""
import collections
import json
import pathlib
import struct
import sys
import zipfile

JAR = pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path(__file__).resolve().parents[1]/'downloads/server-26.3-inner.jar'
NAMES = ('nop aconst_null iconst_m1 iconst_0 iconst_1 iconst_2 iconst_3 iconst_4 iconst_5 lconst_0 lconst_1 fconst_0 fconst_1 fconst_2 dconst_0 dconst_1 bipush sipush ldc ldc_w ldc2_w iload lload fload dload aload iload_0 iload_1 iload_2 iload_3 lload_0 lload_1 lload_2 lload_3 fload_0 fload_1 fload_2 fload_3 dload_0 dload_1 dload_2 dload_3 aload_0 aload_1 aload_2 aload_3 iaload laload faload daload aaload baload caload saload istore lstore fstore dstore astore istore_0 istore_1 istore_2 istore_3 lstore_0 lstore_1 lstore_2 lstore_3 fstore_0 fstore_1 fstore_2 fstore_3 dstore_0 dstore_1 dstore_2 dstore_3 astore_0 astore_1 astore_2 astore_3 iastore lastore fastore dastore aastore bastore castore sastore pop pop2 dup dup_x1 dup_x2 dup2 dup2_x1 dup2_x2 swap iadd ladd fadd dadd isub lsub fsub dsub imul lmul fmul dmul idiv ldiv fdiv ddiv irem lrem frem drem ineg lneg fneg dneg ishl lshl ishr lshr iushr lushr iand land ior lor ixor lxor iinc i2l i2f i2d l2i l2f l2d f2i f2l f2d d2i d2l d2f i2b i2c i2s lcmp fcmpl fcmpg dcmpl dcmpg ifeq ifne iflt ifge ifgt ifle if_icmpeq if_icmpne if_icmplt if_icmpge if_icmpgt if_icmple if_acmpeq if_acmpne goto jsr ret tableswitch lookupswitch ireturn lreturn freturn dreturn areturn return getstatic putstatic getfield putfield invokevirtual invokespecial invokestatic invokeinterface invokedynamic new newarray anewarray arraylength athrow checkcast instanceof monitorenter monitorexit wide multianewarray ifnull ifnonnull goto_w jsr_w').split()
WIDTH = {0x10:2, 0x11:3, 0x12:2, 0x13:3, 0x14:3, **{i:2 for i in range(0x15,0x1a)}, **{i:2 for i in range(0x36,0x3b)}, 0x84:3, **{i:3 for i in range(0x99,0xa9)}, 0xa9:2, **{i:3 for i in range(0xb2,0xb9)}, 0xb9:5, 0xba:5, 0xbb:3, 0xbc:2, 0xbd:3, 0xc0:3, 0xc1:3, 0xc5:4, 0xc6:3, 0xc7:3, 0xc8:5, 0xc9:5}
SUPPORTED = {0x00,0x57,0x59,0x5f,0x6c,0x91,0x92,0x93,*(range(0x02,0x09)),0x10,0x11,0x12,0x13,0x15,*(range(0x1a,0x1e)),0x36,*(range(0x3b,0x3f)),0x60,0x64,0x68,0x70,0x74,0x78,0x7a,0x7c,0x7e,0x80,0x82,0x84,*(range(0x99,0xa5)),0xa7,0xac,0xb8,0xc4}
class R:
 def __init__(self,data): self.d=data; self.p=0
 def take(self,n):
  if n<0 or self.p+n>len(self.d): raise ValueError('truncado')
  b=self.d[self.p:self.p+n];self.p+=n;return b
 def u1(self): return self.take(1)[0]
 def u2(self): return int.from_bytes(self.take(2),'big')
 def u4(self): return int.from_bytes(self.take(4),'big')
def attrs(r):
 for _ in range(r.u2()):
  name=r.u2(); yield name,r.take(r.u4())
def instructions(code):
 p=0
 while p<len(code):
  start=p; op=code[p]
  if op==0xaa:
   a=(p+4)&~3
   if a+12>len(code): raise ValueError('tableswitch truncado')
   low,high=struct.unpack('>ii',code[a+4:a+12]); n=high-low+1
   if n<0 or n>65536: raise ValueError('tableswitch inválido')
   end=a+12+4*n
  elif op==0xab:
   a=(p+4)&~3
   if a+8>len(code): raise ValueError('lookupswitch truncado')
   n=struct.unpack('>i',code[a+4:a+8])[0]
   if n<0 or n>65536: raise ValueError('lookupswitch inválido')
   end=a+8+8*n
  elif op==0xc4:
   if p+1>=len(code): raise ValueError('wide truncado')
   end=p+(6 if code[p+1]==0x84 else 4)
  else:
   if op>=len(NAMES): raise ValueError(f'opcode reservado {op:02x}')
   end=p+WIDTH.get(op,1)
  if end>len(code): raise ValueError('operando truncado')
  yield (start,op,code[p+1:end]); p=end
def parse(data):
 r=R(data)
 if r.u4()!=0xcafebabe: raise ValueError('magic')
 r.take(4); size=r.u2(); cp=[None]*size; i=1
 while i<size:
  t=r.u1()
  if t==1: cp[i]=('utf',r.take(r.u2()).decode('utf-8','replace'))
  elif t in (3,4): r.take(4)
  elif t in (5,6): r.take(8); i+=1
  elif t==7: cp[i]=('class',r.u2())
  elif t==12: cp[i]=('nt',r.u2(),r.u2())
  elif t in (10,11): cp[i]=('method',r.u2(),r.u2())
  elif t in (8,16,19,20): r.take(2)
  elif t in (9,17,18): r.take(4)
  elif t==15: r.take(3)
  else: raise ValueError(f'cp tag {t}')
  i+=1
 def utf(i): return cp[i][1]
 r.take(6);r.take(2*r.u2())
 for _ in range(r.u2()): r.take(6); list(attrs(r))
 methods=[]
 for _ in range(r.u2()):
  flags=r.u2(); name=utf(r.u2()); desc=utf(r.u2())
  for a,data in attrs(r):
   if utf(a)=='Code':
    sub=R(data);sub.take(4); code=sub.take(sub.u4()); methods.append((flags,name,desc,code))
 return cp,methods

def resolve(cp,ix):
 try:
  _,cl,nt=cp[ix];_,nm=cp[cl];_,name,desc=cp[nt];return cp[nm][1],cp[name][1],cp[desc][1]
 except (IndexError,TypeError,ValueError): return None

if __name__ == "__main__":
    counts=collections.Counter(); methods=0; classes=0; failures=[]; candidates=[]; cross_candidates=[]; simple_cross=[]; static_int_methods=[]
    with zipfile.ZipFile(JAR) as z:
     for file in z.namelist():
      if not file.endswith('.class'): continue
      classes+=1
      try:
       cp,ms=parse(z.read(file))
       for flags,name,desc,code in ms:
        inst=list(instructions(code)); methods+=1; counts.update(op for _,op,_ in inst)
        argstr=desc[1:-2] if desc.startswith('(') and len(desc)>2 and desc[-2:][0]==')' and desc[-1] in 'IZBCS' else None
        if flags&8 and argstr is not None and all(x=='I' for x in argstr):
         static_int_methods.append((file[:-6], name, desc))
        if flags&8 and argstr is not None and all(x=='I' for x in argstr) and all(op in SUPPORTED for _,op,_ in inst):
         for _,op,data in inst:
          if op==0xb8:
           ref=resolve(cp,int.from_bytes(data,'big'))
           if ref and ref[0]!=file[:-6] and ref[0].startswith('net/minecraft/') and ref[2].endswith(')I'):
            simple_cross.append({'class':file[:-6], 'method':name, 'descriptor':desc, 'calls':'.'.join(ref[:2])+ref[2]})
        if flags&8 and argstr is not None and all(x=='I' for x in argstr) and any(0x99<=op<=0xa4 or op==0xa7 for _,op,_ in inst) and all(op in SUPPORTED for _,op,_ in inst):
         for _,op,data in inst:
          if op==0xb8:
           ref=resolve(cp,int.from_bytes(data,'big'))
           if ref and ref[2].endswith(')I'):
            cand={'class':file[:-6], 'method':name,'descriptor':desc,'calls':'.'.join(ref[:2])+ref[2]}
            if ref[0]==file[:-6]: candidates.append(cand)
            elif ref[0].startswith('net/minecraft/'): cross_candidates.append(cand)
      except (ValueError,IndexError,struct.error,TypeError) as e:
       failures.append({'class':file,'error':str(e)})
    report={'jar':str(JAR),'classes':classes,'methods_with_code':methods,'instructions':sum(counts.values()),'opcodes':[{'opcode':f'0x{k:02x}','name':NAMES[k],'count':v} for k,v in counts.most_common()], 'same_class_branch_call_candidates':candidates[:40], 'candidate_count':len(candidates), 'cross_class_branch_call_candidates':cross_candidates[:40], 'cross_candidate_count':len(cross_candidates), 'simple_cross_class_candidates':simple_cross[:100], 'simple_cross_candidate_count':len(simple_cross), 'parse_failures':failures, 'warning':'Conteo estático del JAR interno entero; incluye código inalcanzable y no demuestra compatibilidad. No evalúa excepciones ni semántica de llamadas.'}
    report['static_int_methods'] = sum(d.endswith(')I') for _,_,d in static_int_methods)
    report['static_primitive_return_methods'] = len(static_int_methods)
    report['classes_with_static_int_methods'] = len({c for c,_,d in static_int_methods if d.endswith(')I')})
    report['classes_with_static_primitive_return_methods'] = len({c for c,_,_ in static_int_methods})
    if len(sys.argv)>2:
     pathlib.Path(sys.argv[2]).write_text(''.join(f'{c}\t{n}\t{d}\n' for c,n,d in static_int_methods))
    print(json.dumps(report,ensure_ascii=False,indent=2))
