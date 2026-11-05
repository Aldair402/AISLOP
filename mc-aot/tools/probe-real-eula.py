"""Intenta compilar y ejecutar Eula real con archivo verdadero; no implica arranque."""
import hashlib,os,pathlib,subprocess,tempfile,zipfile
root=pathlib.Path(__file__).resolve().parents[2];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
with tempfile.TemporaryDirectory(prefix='mc-eula-real-') as t:
 d=pathlib.Path(t);libs=[]
 with zipfile.ZipFile(root/'downloads/server-26.3.jar') as z:
  lines=z.read('META-INF/libraries.list').decode()
  for i,l in enumerate(lines.splitlines()):
   sha,name,path=l.split('\t');b=z.read('META-INF/libraries/'+path);assert hashlib.sha256(b).hexdigest()==sha
   p=d/f'{i}.jar';p.write_bytes(b);libs.append((path,p))
 source='''package net.minecraft.test;import java.nio.file.*;import net.minecraft.server.Eula;public class EulaProbe{public static int run(){return new Eula(Path.of("eula.txt")).hasAgreedToEULA()?1:0;}}'''
 (d/'EulaProbe.java').write_text(source);(d/'Driver.java').write_text('import net.minecraft.test.EulaProbe;public class Driver{public static void main(String[]x){System.out.println(EulaProbe.run());}}')
 cp=os.pathsep.join([str(root/'downloads/server-26.3-inner.jar'),*[str(p) for _,p in libs]])
 subprocess.run([str(jdk/'javac'),'-cp',cp,'-d',str(d/'classes'),str(d/'EulaProbe.java'),str(d/'Driver.java')],check=True)
 with zipfile.ZipFile(root/'downloads/server-26.3-inner.jar') as src, zipfile.ZipFile(d/'version.jar','w') as dst:
  for i in src.infolist():dst.writestr(i,src.read(i.filename))
  dst.write(d/'classes/net/minecraft/test/EulaProbe.class','net/minecraft/test/EulaProbe.class')
 with zipfile.ZipFile(d/'bundle.jar','w') as z:
  b=(d/'version.jar').read_bytes();z.writestr('META-INF/versions.list',f'{hashlib.sha256(b).hexdigest()}\tversion\tv/version.jar\n');z.writestr('META-INF/versions/v/version.jar',b);z.writestr('META-INF/libraries.list',lines)
  for path,p in libs:z.writestr('META-INF/libraries/'+path,p.read_bytes())
 env=os.environ.copy();env['MC_AOT_REFLECT_CLASSES']='org/apache/logging/slf4j/SLF4JServiceProvider'+(':'+env['MC_AOT_EULA_EXTRA_REFLECT_CLASSES'] if env.get('MC_AOT_EULA_EXTRA_REFLECT_CLASSES') else '');env['MC_AOT_DIAGNOSTIC_DISPATCH_PREFIXES']='net/minecraft/server/,org/slf4j/,org/apache/logging/,com/mojang/logging/';env['MC_AOT_GUARD_MINECRAFT_LAMBDAS']='1';env['MC_AOT_DISABLE_JFR']='1';env['MC_AOT_JAVA_PROCESSORS']='3';env['MC_AOT_STANDARD_SYSTEM_LOADER']='1'
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'mc-aot/Cargo.toml'),'--','multi-static-demo',str(d/'bundle.jar'),'net/minecraft/test/EulaProbe',str(d/'native'),'run','()I'],capture_output=True,text=True,env=env)
 print(p.stderr,end='');print('compile_exit=',p.returncode)
 if p.returncode:raise SystemExit(p.returncode)
 (d/'eula.txt').write_text('eula=true\n')
 j=subprocess.run([str(jdk/'java'),'-XX:-FlightRecorder','-XX:ActiveProcessorCount=3','-cp',os.pathsep.join([str(d/'classes'),cp]),'Driver'],cwd=d,capture_output=True,text=True,env=env)
 n=subprocess.run([str(d/'native'),'0'],cwd=d,capture_output=True,text=True,env=env)
 print('Java:',j.returncode,repr(j.stdout),j.stderr);print('native:',n.returncode,repr(n.stdout),n.stderr)
 if j.returncode!=0 or n.returncode!=0 or j.stdout!=n.stdout:raise SystemExit(1)
 print('OK: Eula real acepta eula=true')
