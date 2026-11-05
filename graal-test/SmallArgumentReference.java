import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import net.minecraft.test.SmallFixture;
public class SmallArgumentReference {
    private static Method method(String cls,String name,Class<?>... args) throws Exception {
        Method m=Class.forName(cls).getDeclaredMethod(name,args);m.setAccessible(true);return m;
    }
    public static void main(String[] args) throws Exception {
        Method flags=method("net.minecraft.commands.synchronization.ArgumentUtils","createNumberFlags",boolean.class,boolean.class);
        Method min=method("net.minecraft.commands.synchronization.ArgumentUtils","numberHasMin",byte.class);
        Method x=method("net.minecraft.core.SectionPos","sectionRelativeX",short.class);
        Method continuation=method("net.minecraft.network.VarInt","hasContinuationBit",byte.class);
        Method path=method("net.minecraft.resources.Identifier","validPathChar",char.class);
        var in=new BufferedReader(new InputStreamReader(System.in));
        for(String line;(line=in.readLine())!=null;) {
            String[] p=line.split(","); int a=Integer.parseInt(p[1]);
            Object out=switch(p[0]) {
                case "flags" -> flags.invoke(null,a!=0,Integer.parseInt(p[2])!=0);
                case "min" -> min.invoke(null,(byte)a);
                case "x" -> x.invoke(null,(short)a);
                case "continuation" -> continuation.invoke(null,(byte)a);
                case "path" -> path.invoke(null,(char)a);
                case "nested" -> SmallFixture.nested(a!=0,(byte)Integer.parseInt(p[2]),(char)Integer.parseInt(p[3]),(short)Integer.parseInt(p[4]));
                default -> throw new IllegalArgumentException();
            };
            System.out.println(out instanceof Boolean b ? (b?1:0) : out);
        }
    }
}
