import java.io.BufferedReader;
import java.io.InputStreamReader;
import net.minecraft.core.SectionPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.server.level.ChunkTrackingView;
import net.minecraft.test.LongFixture;
public class LongReference {
  public static void main(String[] args) throws Exception {
    var bounds=Class.forName("net.minecraft.util.PngInfo").getDeclaredMethod("validateBounds",int.class,int.class,byte.class,byte.class);
    bounds.setAccessible(true);
    var wrap=Class.forName("net.minecraft.server.commands.TimeCommand").getDeclaredMethod("wrapTime",long.class);
    wrap.setAccessible(true);
    var in=new BufferedReader(new InputStreamReader(System.in));
    for(String line;(line=in.readLine())!=null;) {
      String[] p=line.split(",");
      try {
        long v=switch(p[0]) {
          case "wrap" -> (int)wrap.invoke(null,Long.parseLong(p[1]));
          case "exact" -> LongFixture.exact(Long.parseLong(p[1]));
          case "pre" -> LongFixture.pre(Long.parseLong(p[1]));
          case "distance" -> ChunkTrackingView.isWithinDistance(Integer.parseInt(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]),Integer.parseInt(p[4]),Integer.parseInt(p[5]),Integer.parseInt(p[6])!=0)?1:0;
          case "bounds" -> ((boolean)bounds.invoke(null,Integer.parseInt(p[1]),Integer.parseInt(p[2]),(byte)Integer.parseInt(p[3]),(byte)Integer.parseInt(p[4])))?1:0;
          case "floorl" -> LongFixture.floorl(Long.parseLong(p[1]),Long.parseLong(p[2]));
          case "modl" -> LongFixture.modl(Long.parseLong(p[1]),Long.parseLong(p[2]));
          case "floori" -> LongFixture.floori(Integer.parseInt(p[1]),Integer.parseInt(p[2]));
          case "modi" -> LongFixture.modi(Integer.parseInt(p[1]),Integer.parseInt(p[2]));
          case "sx" -> SectionPos.x(Long.parseLong(p[1]));
          case "sy" -> SectionPos.y(Long.parseLong(p[1]));
          case "sz" -> SectionPos.z(Long.parseLong(p[1]));
          case "sectionpack" -> SectionPos.asLong(Integer.parseInt(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]));
          case "offset" -> SectionPos.offset(Long.parseLong(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3]),Integer.parseInt(p[4]));
          case "chunkpack" -> ChunkPos.pack(Integer.parseInt(p[1]),Integer.parseInt(p[2]));
          case "cx" -> ChunkPos.getX(Long.parseLong(p[1]));
          case "cz" -> ChunkPos.getZ(Long.parseLong(p[1]));
          case "sectionchunk" -> ChunkPos.fromSectionNode(Long.parseLong(p[1]));
          case "arith" -> LongFixture.arith(Long.parseLong(p[1]),Long.parseLong(p[2]));
          case "div" -> LongFixture.div(Long.parseLong(p[1]),Long.parseLong(p[2]));
          case "rem" -> LongFixture.rem(Long.parseLong(p[1]),Long.parseLong(p[2]));
          case "shl" -> LongFixture.shl(Long.parseLong(p[1]),Integer.parseInt(p[2]));
          case "shr" -> LongFixture.shr(Long.parseLong(p[1]),Integer.parseInt(p[2]));
          case "ushr" -> LongFixture.ushr(Long.parseLong(p[1]),Integer.parseInt(p[2]));
          case "cmp" -> LongFixture.cmp(Long.parseLong(p[1]),Long.parseLong(p[2]));
          case "mix" -> LongFixture.mix(Integer.parseInt(p[1]),Long.parseLong(p[2]),Integer.parseInt(p[3]));
          case "loop" -> LongFixture.loop(Long.parseLong(p[1]),Integer.parseInt(p[2]));
          case "choose" -> LongFixture.choose(Long.parseLong(p[1]),Integer.parseInt(p[2]));
          case "twice" -> LongFixture.twice(Long.parseLong(p[1]));
          default -> throw new IllegalArgumentException();
        };
        System.out.println(v);
      } catch(ArithmeticException e) {System.out.println("ERR_ARITHMETIC");}
    }
  }
}
