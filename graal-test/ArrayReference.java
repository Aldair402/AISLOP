import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import net.minecraft.Optionull;
import net.minecraft.server.rcon.PktUtils;
import net.minecraft.test.ArrayFixture;

public class ArrayReference {
  static String[] parts(String s) {
    if(s.equals("null")) return null;
    String inner=s.substring(1,s.length()-1).trim();
    return inner.isEmpty()?new String[0]:inner.split(",");
  }
  static int[] ai(String s) {String[] p=parts(s);if(p==null)return null;int[] a=new int[p.length];for(int i=0;i<a.length;i++)a[i]=Integer.parseInt(p[i].trim());return a;}
  static long[] aj(String s) {String[] p=parts(s);if(p==null)return null;long[] a=new long[p.length];for(int i=0;i<a.length;i++)a[i]=Long.parseLong(p[i].trim());return a;}
  static byte[] ab(String s) {String[] p=parts(s);if(p==null)return null;byte[] a=new byte[p.length];for(int i=0;i<a.length;i++)a[i]=Byte.parseByte(p[i].trim());return a;}
  static short[] as(String s) {String[] p=parts(s);if(p==null)return null;short[] a=new short[p.length];for(int i=0;i<a.length;i++)a[i]=Short.parseShort(p[i].trim());return a;}
  static char[] ac(String s) {String[] p=parts(s);if(p==null)return null;char[] a=new char[p.length];for(int i=0;i<a.length;i++)a[i]=(char)Integer.parseInt(p[i].trim());return a;}
  static boolean[] az(String s) {String[] p=parts(s);if(p==null)return null;boolean[] a=new boolean[p.length];for(int i=0;i<a.length;i++)a[i]=!p[i].trim().equals("0");return a;}
  public static void main(String[] args) throws Exception {
    Method biome=Class.forName("net.minecraft.util.datafix.fixes.ChunkHeightAndBiomeFix").getDeclaredMethod("getOldBiome",int[].class,int.class);biome.setAccessible(true);
    var in=new BufferedReader(new InputStreamReader(System.in));
    for(String line;(line=in.readLine())!=null;) {
      String[] p=line.split("\\|",-1);
      try {
        long out=switch(p[0]) {
          case "optI" -> Optionull.isNullOrEmpty(ai(p[1]))?1:0;
          case "optJ" -> Optionull.isNullOrEmpty(aj(p[1]))?1:0;
          case "optB" -> Optionull.isNullOrEmpty(ab(p[1]))?1:0;
          case "optC" -> Optionull.isNullOrEmpty(ac(p[1]))?1:0;
          case "optS" -> Optionull.isNullOrEmpty(as(p[1]))?1:0;
          case "optZ" -> Optionull.isNullOrEmpty(az(p[1]))?1:0;
          case "little" -> PktUtils.intFromByteArray(ab(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "little2" -> PktUtils.intFromByteArray(ab(p[1]),Integer.parseInt(p[2]));
          case "big" -> PktUtils.intFromNetworkByteArray(ab(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "biome" -> (int)biome.invoke(null,ai(p[1]),Integer.parseInt(p[2]));
          case "sum" -> ArrayFixture.sum(ai(p[1]));
          case "wi" -> ArrayFixture.writeInt(ai(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "wj" -> ArrayFixture.writeLong(aj(p[1]),Integer.parseInt(p[2]),Long.parseLong(p[3]));
          case "wb" -> ArrayFixture.writeByte(ab(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "wc" -> ArrayFixture.writeChar(ac(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "ws" -> ArrayFixture.writeShort(as(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "wz" -> ArrayFixture.writeBool(az(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3])!=0);
          case "defaults" -> ArrayFixture.defaults(Integer.parseInt(p[1]));
          case "alloc" -> ArrayFixture.allocate(Integer.parseInt(p[1]),Integer.parseInt(p[2]));
          case "allocJ" -> ArrayFixture.allocateLong(Integer.parseInt(p[1]),Long.parseLong(p[2]));
          case "alias" -> ArrayFixture.alias(ai(p[1]),Integer.parseInt(p[2]));
          case "same" -> {int[] a=ai(p[1]);int[] b=p[2].equals("@0")?a:ai(p[2]);yield ArrayFixture.same(a,b);}
          case "nullref" -> ArrayFixture.nullref();
          default -> throw new IllegalArgumentException(p[0]);
        };
        System.out.println(out);
      } catch(Throwable e) {
        Throwable cause=e instanceof InvocationTargetException && e.getCause()!=null?e.getCause():e;
        System.out.println("ERR:"+cause.getClass().getSimpleName());
      }
    }
  }
}
