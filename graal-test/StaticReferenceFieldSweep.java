import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
public class StaticReferenceFieldSweep {
 public static void main(String[] args)throws Exception {
  var out=System.err;var in=new BufferedReader(new InputStreamReader(System.in));
  for(String line;(line=in.readLine())!=null;) {
   String[] p=line.split("\\t");
   try {
    Field f=Class.forName(p[0].replace('/','.')).getDeclaredField(p[1]);f.setAccessible(true);
    Object v=f.get(null);if(v instanceof Boolean b)v=b?1:0;if(v instanceof Character c)v=(int)c;
    String text=v instanceof Float x?String.format("fbits:%08x",Float.floatToRawIntBits(x)):v instanceof Double x?String.format("dbits:%016x",Double.doubleToRawLongBits(x)):String.valueOf(v);String encoded=Base64.getEncoder().encodeToString(text.getBytes(StandardCharsets.UTF_8));
    out.println("MCRESULT\tOK\t"+encoded);
   }catch(Throwable e){out.println("MCRESULT\tERROR\t"+e.getClass().getName());}
  }
 }
}
