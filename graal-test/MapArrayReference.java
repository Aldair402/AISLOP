import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.InvocationTargetException;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
public class MapArrayReference {
  public static void main(String[] args) throws Exception {
    var resultStream=System.err;
    SharedConstants.tryDetectVersion();
    Bootstrap.bootStrap();
    var m=Class.forName("net.minecraft.world.item.MapItem").getDeclaredMethod("isBiomeWatery",boolean[].class,int.class,int.class);m.setAccessible(true);
    var in=new BufferedReader(new InputStreamReader(System.in));
    for(String line;(line=in.readLine())!=null;) {
      String[] p=line.split("\\|",-1); boolean[] a;
      if(p[0].equals("null")) a=null;
      else {String inner=p[0].substring(1,p[0].length()-1);String[] bits=inner.isEmpty()?new String[0]:inner.split(",");a=new boolean[bits.length];for(int i=0;i<a.length;i++)a[i]=bits[i].equals("1");}
      try {boolean r=(boolean)m.invoke(null,a,Integer.parseInt(p[1]),Integer.parseInt(p[2]));resultStream.println("MCRESULT\t"+(r?1:0));}
      catch(InvocationTargetException e){resultStream.println("MCRESULT\tERROR:"+e.getCause().getClass().getSimpleName());}
    }
  }
}
