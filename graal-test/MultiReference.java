import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Constructor;
import java.util.ArrayList;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.flag.FeatureFlagUniverse;
public class MultiReference {
    public static void main(String[] args) throws Exception {
        Constructor<?> a=Class.forName("net.minecraft.world.level.LevelHeightAccessor$1").getDeclaredConstructor(int.class,int.class);
        Constructor<?> b=Class.forName("net.minecraft.world.level.levelgen.BelowZeroRetrogen$1").getDeclaredConstructor();
        a.setAccessible(true); b.setAccessible(true);
        var input=new BufferedReader(new InputStreamReader(System.in));
        for(String line; (line=input.readLine())!=null;) {
            String[] p=line.split(" "); int i=0;var refs=new ArrayList<Object>();var out=new ArrayList<String>();
            while(i<p.length) {
                switch(p[i++]) {
                    case "new" -> {
                        int type=Integer.parseInt(p[i++]);LevelHeightAccessor object;
                        if(type==0) object=(LevelHeightAccessor)a.newInstance(Integer.parseInt(p[i++]),Integer.parseInt(p[i++]));
                        else object=(LevelHeightAccessor)b.newInstance();
                        out.add(Integer.toString(refs.size()));refs.add(object);
                    }
                    case "copy" -> {var object=refs.get(Integer.parseInt(p[i++]));out.add(Integer.toString(refs.size()));refs.add(object);}
                    case "null" -> {out.add(Integer.toString(refs.size()));refs.add(null);}
                    case "eq" -> {var x=refs.get(Integer.parseInt(p[i++]));var y=refs.get(Integer.parseInt(p[i++]));out.add(x==y?"1":"0");}
                    case "string" -> {String value=new String(p[i++]);out.add(Integer.toString(refs.size()));refs.add(value);}
                    case "newref" -> {String value=(String)refs.get(Integer.parseInt(p[i++]));var obj=new FeatureFlagUniverse(value);out.add(Integer.toString(refs.size()));refs.add(obj);}
                    case "getref" -> {var obj=(FeatureFlagUniverse)refs.get(Integer.parseInt(p[i++]));if(obj==null){out.add("ERR_NULL");i=p.length;break;}out.add(Integer.toString(refs.size()));refs.add(obj.toString());}
                    case "text" -> {var value=(String)refs.get(Integer.parseInt(p[i++]));if(value==null){out.add("ERR_NULL");i=p.length;break;}out.add(value);}
                    case "call" -> {
                        var obj=(LevelHeightAccessor)refs.get(Integer.parseInt(p[i++]));String method=p[i++];
                        if(obj==null) {out.add("ERR_NULL"); i=p.length; break;}
                        int result=switch(method) {case "getHeight"->obj.getHeight(); case "getMinY"->obj.getMinY(); case "getMaxY"->obj.getMaxY(); default->throw new IllegalArgumentException(method);};
                        out.add(Integer.toString(result));
                    }
                    default -> throw new IllegalArgumentException("unsupported");
                }
            }
            System.out.println(String.join(",",out));
        }
    }
}
