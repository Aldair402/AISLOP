import java.lang.reflect.Constructor;
public class ReferenceSweep {
 public static void main(String[] args) throws Exception {
  for (int i=0;i<args.length;i+=2) {
   Class<?> type=Class.forName(args[i]);Constructor<?> c=type.getDeclaredConstructor(String.class);c.setAccessible(true);
   var getter=type.getDeclaredMethod(args[i+1]);getter.setAccessible(true);
   String source=new String("Alpha"), second=new String("Alpha");
   Object one=c.newInstance(source), result=getter.invoke(one), other=c.newInstance((Object)null), nullResult=getter.invoke(other);
   System.out.println("0,1,2,"+(source==result?1:0)+","+result+",3,"+(second==result?1:0)+",4,5,6,"+(nullResult==null?1:0));
  }
 }
}
