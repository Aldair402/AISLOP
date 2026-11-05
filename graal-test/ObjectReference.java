import java.io.BufferedReader;
import java.io.InputStreamReader;
import net.minecraft.world.level.LevelHeightAccessor;
public class ObjectReference {
    public static void main(String[] args) throws Exception {
        var type = Class.forName("net.minecraft.world.level.LevelHeightAccessor$1");
        var constructor = type.getDeclaredConstructor(int.class, int.class);
        constructor.setAccessible(true);
        var input = new BufferedReader(new InputStreamReader(System.in));
        for (String line; (line = input.readLine()) != null;) {
            String[] parts = line.split(",");
            int height = Integer.parseInt(parts[0]);
            int minY = Integer.parseInt(parts[1]);
            var object = (LevelHeightAccessor) constructor.newInstance(height, minY);
            System.out.println(object.getHeight() + "," + object.getMinY() + "," + object.getMaxY() + "," + object.getHeight());
        }
    }
}
