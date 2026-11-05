import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import net.minecraft.test.SwitchFixture;

public class SwitchReference {
    public static void main(String[] args) throws Exception {
        Class<?> c = Class.forName("net.minecraft.util.PngInfo");
        Method depth = c.getDeclaredMethod("validateBitDepth", int.class);
        Method color = c.getDeclaredMethod("validateColorType", int.class);
        depth.setAccessible(true); color.setAccessible(true);
        var in = new BufferedReader(new InputStreamReader(System.in));
        for (String line; (line=in.readLine()) != null;) {
            int x = Integer.parseInt(line);
            System.out.println(((boolean)depth.invoke(null,x) ? 1 : 0) + "," +
                ((boolean)color.invoke(null,x) ? 1 : 0) + "," +
                SwitchFixture.table(x) + "," + SwitchFixture.lookup(x) + "," +
                SwitchFixture.nested(x));
        }
    }
}
