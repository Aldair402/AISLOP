import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.function.IntSupplier;
import net.minecraft.util.Mth;
import net.minecraft.util.LightCoordsUtil;
import net.minecraft.util.ARGB;
public class MthReference {
    private static String result(IntSupplier f) {
        try { return Integer.toString(f.getAsInt()); }
        catch (ArithmeticException e) { return "ERR_ARITHMETIC"; }
    }
    public static void main(String[] args) throws Exception {
        var in = new BufferedReader(new InputStreamReader(System.in));
        var origin = Mth.class.getDeclaredMethod("lambda$outFromOrigin$1", int.class, int.class, int.class, int.class, int.class);
        origin.setAccessible(true);
        var quantize = Class.forName("net.minecraft.server.commands.FillBiomeCommand").getDeclaredMethod("quantize", int.class);
        quantize.setAccessible(true);
        var tickDelay = Class.forName("net.minecraft.world.entity.ai.goal.Goal").getDeclaredMethod("reducedTickDelay", int.class);
        tickDelay.setAccessible(true);
        for (String line; (line = in.readLine()) != null;) {
            String[] parts = line.split(",");
            int x = Integer.parseInt(parts[0]), y = Integer.parseInt(parts[1]), z = Integer.parseInt(parts[2]);
            int w = Integer.parseInt(parts[3]), v = Integer.parseInt(parts[4]);
            System.out.println(Mth.square(x) + "," + Mth.smallestEncompassingPowerOfTwo(x)
                + "," + Mth.abs(x) + "," + Mth.absMax(x, y)
                + "," + Mth.clamp(x, y, z) + "," + Mth.murmurHash3Mixer(x)
                + "," + Mth.wrapDegrees(x) + "," + result(() -> Mth.positiveCeilDiv(x,y))
                + "," + result(() -> Mth.roundToward(x,y)) + "," + result(() -> Mth.floorDiv(x,y))
                + "," + result(() -> Mth.positiveModulo(x,y)) + "," + origin.invoke(null,x,y,z,w,v)
                + "," + LightCoordsUtil.lightCoordsWithEmission(x,y) + "," + LightCoordsUtil.smoothBlend(x,y,z,w)
                + "," + quantize.invoke(null,x) + "," + tickDelay.invoke(null,x)
                + "," + ARGB.multiply(x,y) + "," + ARGB.average(x,y) + "," + ARGB.alphaBlend(x,y)
                + "," + (Mth.isPowerOfTwo(x) ? 1 : 0));
        }
    }
}
