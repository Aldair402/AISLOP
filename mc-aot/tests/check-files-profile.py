#!/usr/bin/env python3
"""Path.of y Files.writeString predeterminado, positivo y guardas, Linux."""
import os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1];jdk=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
src='''package net.minecraft.test;import java.nio.file.*;import java.io.IOException;public class FilesDemo{public static int run(int n) throws IOException{Path p=Path.of("test-dir//",n%2==0?"a.txt":"b.txt");Path q=Files.writeString(p,n%3==0?"Hé🚀":"ABC");return (p==q?100:0)+p.toString().length()+(p.toString()==p.toString()?10:0);}public static int bad(){try{Files.writeString(Path.of("missing/file"),"x");return 0;}catch(NoSuchFileException e){return e.getMessage().length();}catch(IOException e){return -1;}}}'''
driver='''import net.minecraft.test.FilesDemo;public class FileDriver{public static void main(String[]a)throws Exception{for(String x:a)System.out.println(FilesDemo.run(Integer.parseInt(x)));System.out.println(FilesDemo.bad());}}'''
with tempfile.TemporaryDirectory(prefix='mc-files-') as t:
 d=pathlib.Path(t);(d/'FilesDemo.java').write_text(src);(d/'FileDriver.java').write_text(driver);subprocess.run([str(jdk/'javac'),'-d',str(d),str(d/'FilesDemo.java'),str(d/'FileDriver.java')],check=True);subprocess.run([str(jdk/'jar'),'cf',str(d/'fixture.jar'),'-C',str(d),'net'],check=True)
 p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(root/'Cargo.toml'),'--','multi-static-demo',str(d/'fixture.jar'),'net/minecraft/test/FilesDemo',str(d/'native'),'run','(I)I','bad','()I'],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 a=d/'java';b=d/'native-dir';(a/'test-dir').mkdir(parents=True);(b/'test-dir').mkdir(parents=True);vals=list(range(40));j=subprocess.run([str(jdk/'java'),'-cp',str(d),'FileDriver',*map(str,vals)],cwd=a,capture_output=True,text=True,check=True);native=subprocess.run([str(d/'native'),*[v for n in vals for v in ('0',str(n))],'1'],cwd=b,capture_output=True,text=True)
 if native.returncode or j.stdout!=native.stdout:raise AssertionError((native.returncode,j.stdout,native.stdout,native.stderr))
 for name in ['a.txt','b.txt']:
  if (a/'test-dir'/name).read_bytes()!=(b/'test-dir'/name).read_bytes():raise AssertionError(name)
 print('OK: 40 escrituras UTF-8 reales, identidad Path y contenido comparados con Java; NoSuchFileException y mensaje contrastados')
