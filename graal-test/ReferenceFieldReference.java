import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import net.minecraft.world.flag.FeatureFlagUniverse;
public class ReferenceFieldReference {
 public static void main(String[] args) throws Exception {
  var in=new BufferedReader(new InputStreamReader(System.in));
  for(String line;(line=in.readLine())!=null;){
   String[] p=line.split(" ");int i=0;var refs=new ArrayList<Object>();var out=new ArrayList<String>();
   while(i<p.length){
    switch(p[i++]){
     case "string" -> {String s=new String(p[i++]);out.add(Integer.toString(refs.size()));refs.add(s);}
     case "null" -> {out.add(Integer.toString(refs.size()));refs.add(null);}
     case "copy" -> {Object value=refs.get(Integer.parseInt(p[i++]));out.add(Integer.toString(refs.size()));refs.add(value);}
     case "new" -> {String s=(String)refs.get(Integer.parseInt(p[i++]));var obj=new FeatureFlagUniverse(s);out.add(Integer.toString(refs.size()));refs.add(obj);}
     case "get" -> {var obj=(FeatureFlagUniverse)refs.get(Integer.parseInt(p[i++]));if(obj==null){out.add("ERR_NULL");i=p.length;break;}String value=obj.toString();out.add(Integer.toString(refs.size()));refs.add(value);}
     case "eq" -> {Object a=refs.get(Integer.parseInt(p[i++])), b=refs.get(Integer.parseInt(p[i++]));out.add(a==b?"1":"0");}
     case "text" -> {String s=(String)refs.get(Integer.parseInt(p[i++]));if(s==null){out.add("ERR_NULL");i=p.length;break;}out.add(s);}
     default -> throw new IllegalArgumentException();
    }
   }
   System.out.println(String.join(",",out));
  }
 }
}
