import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Field;
public class StaticSweepReference {
 public static void main(String[] a) throws Exception {
  var out=System.err; var in=new BufferedReader(new InputStreamReader(System.in));
  for(String line;(line=in.readLine())!=null;) {
   String[] p=line.split("\\t");
   try {
    Field f=Class.forName(p[0].replace('/','.')).getDeclaredField(p[1]);f.setAccessible(true);
    Object v=f.get(null);if(v instanceof Boolean b)v=b?1:0;if(v instanceof Character c)v=(int)c;
    out.println("MCRESULT\t"+v);
   } catch(Throwable e) {out.println("MCRESULT\tERROR:"+e.getClass().getName());}
  }
 }
}
