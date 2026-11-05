import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[2];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-provider-init-') as t:
 d=pathlib.Path(t);libs=[]
 with zipfile.ZipFile(root/'downloads/server-26.3.jar') as z:
  lines=z.read('META-INF/libraries.list').decode()
  for i,l in enumerate(lines.splitlines()):
   sha,name,path=l.split('\t');b=z.read('META-INF/libraries/'+path)
   assert hashlib.sha256(b).hexdigest()==sha
   p=d/f'{i}.jar';p.write_bytes(b);libs.append((path,p))
 source='''package net.minecraft.test;import org.apache.logging.slf4j.SLF4JServiceProvider;public class InitProbe{public static int run(){SLF4JServiceProvider p=new SLF4JServiceProvider();p.initialize();return p.getLoggerFactory()!=null?1:0;}}'''
 (d/'InitProbe.java').write_text(source)
 (d/'Driver.java').write_text('import net.minecraft.test.InitProbe;public class Driver{public static void main(String[] x){System.out.println(InitProbe.run());}}')
 subprocess.run([str(jdk/'javac'),'-cp',os.pathsep.join(str(p) for _,p in libs),'-d',str(d/'classes'),str(d/'InitProbe.java'),str(d/'Driver.java')],check=True)
 subprocess.run([str(jdk/'jar'),'cf',str(d/'version.jar'),'-C',str(d/'classes'),'.'],check=True)
 with zipfile.ZipFile(d/'bundle.jar','w') as z:
  b=(d/'version.jar').read_bytes();z.writestr('META-INF/versions.list',f'{hashlib.sha256(b).hexdigest()}\tversion\tv/version.jar\n');z.writestr('META-INF/versions/v/version.jar',b);z.writestr('META-INF/libraries.list',lines)
  for path,p in libs:z.writestr('META-INF/libraries/'+path,p.read_bytes())
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','multi-static-demo',str(d/'bundle.jar'),'net/minecraft/test/InitProbe',str(d/'native'),'run','()I'],capture_output=True,text=True)
 print(p.stderr,end='');print('compile_exit=',p.returncode)
 if p.returncode==0:
  (pathlib.Path('/var/tmp')/'mc-provider-init-debug.rs').write_text((d/'native.rs').read_text())
  env={k:v for k,v in os.environ.items() if not k.lower().startswith(('log4j','org_apache_logging_log4j'))};env.pop('MC_AOT_JAVA_PROPERTIES',None)
  j=subprocess.run([str(jdk/'java'),'-cp',os.pathsep.join([str(d/'classes'),*[str(p) for _,p in libs]]),'Driver'],capture_output=True,text=True,env=env)
  n=subprocess.run([str(d/'native'),'0'],capture_output=True,text=True,env=env)
  print('Java:',j.returncode,repr(j.stdout),j.stderr);print('native:',n.returncode,repr(n.stdout),n.stderr)
  if j.returncode!=0 or n.returncode!=0 or j.stdout!=n.stdout:raise SystemExit(1)
  env['MC_AOT_JAVA_PROPERTIES']='log4j2.StatusLogger.dateFormat=yyyy'
  configured=subprocess.run([str(d/'native'),'0'],capture_output=True,text=True,env=env)
  if configured.returncode==0 or 'DateTimeFormatter.ofPattern' not in configured.stderr:raise AssertionError((configured.returncode,configured.stdout,configured.stderr))
  print('OK: inicialización real del proveedor SLF4J con configuración predeterminada; formato configurado rechazado explícitamente')
 else:raise SystemExit(p.returncode)

