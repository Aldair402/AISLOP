import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.lang.reflect.InvocationTargetException;
import java.util.HashMap;
import java.util.Map;
public class LongSweepReference {
  public static void main(String[] args) throws Exception {
    var in=new BufferedReader(new InputStreamReader(System.in));
    Map<String,Method> cache=new HashMap<>();
    for(String line;(line=in.readLine())!=null;) {
      String[] p=line.split("\\t",-1);
      try {
        String key=p[0]+"."+p[1]+p[2];
        Method m=cache.get(key);
        String raw=p[2].substring(1,p[2].indexOf(')'));
        Class<?>[] types=new Class<?>[raw.length()];Object[] values=new Object[raw.length()];
        String[] a=p[3].isEmpty()?new String[0]:p[3].split(",");
        for(int i=0;i<types.length;i++) {
          long x=Long.parseLong(a[i]);
          switch(raw.charAt(i)) {
            case 'I' -> {types[i]=int.class;values[i]=(int)x;}
            case 'J' -> {types[i]=long.class;values[i]=x;}
            case 'Z' -> {types[i]=boolean.class;values[i]=x!=0;}
            case 'B' -> {types[i]=byte.class;values[i]=(byte)x;}
            case 'C' -> {types[i]=char.class;values[i]=(char)x;}
            case 'S' -> {types[i]=short.class;values[i]=(short)x;}
            default -> throw new IllegalArgumentException("descriptor");
          }
        }
        if(m==null) {m=Class.forName(p[0].replace('/','.')).getDeclaredMethod(p[1],types);m.setAccessible(true);cache.put(key,m);}
        Object out=m.invoke(null,values);
        if(out instanceof Boolean b)out=b?1:0;
        if(out instanceof Character c)out=(int)c;
        System.err.println("MCRESULT\t"+out);
      } catch(Throwable e) {
        Throwable cause=e instanceof InvocationTargetException && e.getCause()!=null?e.getCause():e;
        System.err.println("MCRESULT\tERROR:"+cause.getClass().getName());
      }
    }
  }
}
