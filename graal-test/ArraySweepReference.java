import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Map;
public class ArraySweepReference {
  static Object array(char t,String text) {
    if(text.equals("null"))return null;
    String inside=text.substring(1,text.length()-1);
    String[] p=inside.isEmpty()?new String[0]:inside.split(",");
    return switch(t) {
      case 'I' -> {int[] a=new int[p.length];for(int i=0;i<a.length;i++)a[i]=Integer.parseInt(p[i]);yield a;}
      case 'J' -> {long[] a=new long[p.length];for(int i=0;i<a.length;i++)a[i]=Long.parseLong(p[i]);yield a;}
      case 'B' -> {byte[] a=new byte[p.length];for(int i=0;i<a.length;i++)a[i]=Byte.parseByte(p[i]);yield a;}
      case 'S' -> {short[] a=new short[p.length];for(int i=0;i<a.length;i++)a[i]=Short.parseShort(p[i]);yield a;}
      case 'C' -> {char[] a=new char[p.length];for(int i=0;i<a.length;i++)a[i]=(char)Integer.parseInt(p[i]);yield a;}
      case 'Z' -> {boolean[] a=new boolean[p.length];for(int i=0;i<a.length;i++)a[i]=p[i].equals("1");yield a;}
      default -> throw new IllegalArgumentException("tipo");
    };
  }
  public static void main(String[] args) throws Exception {
    var in=new BufferedReader(new InputStreamReader(System.in));Map<String,Method> methods=new HashMap<>();
    for(String line;(line=in.readLine())!=null;) {
      String[] p=line.split("\\t",-1);
      try {
        String key=p[0]+"."+p[1]+p[2], raw=p[2].substring(1,p[2].indexOf(')'));
        String[] v=p[3].isEmpty()?new String[0]:p[3].split("\\|",-1);
        var types=new java.util.ArrayList<Class<?>>();var values=new java.util.ArrayList<Object>();
        for(int i=0,j=0;i<raw.length();i++,j++) {
          char t=raw.charAt(i);
          if(t=='[') {t=raw.charAt(++i);Object a=array(t,v[j]);values.add(a);types.add(switch(t){case 'I'->int[].class;case 'J'->long[].class;case 'B'->byte[].class;case 'S'->short[].class;case 'C'->char[].class;case 'Z'->boolean[].class;default->throw new IllegalArgumentException();});}
          else {long x=Long.parseLong(v[j]);switch(t){case 'I'->{types.add(int.class);values.add((int)x);}case 'J'->{types.add(long.class);values.add(x);}case 'Z'->{types.add(boolean.class);values.add(x!=0);}case 'B'->{types.add(byte.class);values.add((byte)x);}case 'C'->{types.add(char.class);values.add((char)x);}case 'S'->{types.add(short.class);values.add((short)x);}default->throw new IllegalArgumentException();}}
        }
        Method m=methods.get(key);if(m==null){m=Class.forName(p[0].replace('/','.')).getDeclaredMethod(p[1],types.toArray(Class[]::new));m.setAccessible(true);methods.put(key,m);}
        Object out=m.invoke(null,values.toArray());if(out instanceof Boolean b)out=b?1:0;if(out instanceof Character c)out=(int)c;
        System.err.println("MCRESULT\t"+out);
      } catch(Throwable e) {Throwable cause=e instanceof InvocationTargetException && e.getCause()!=null?e.getCause():e;System.err.println("MCRESULT\tERROR:"+cause.getClass().getSimpleName());}
    }
  }
}
