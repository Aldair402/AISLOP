import java.lang.reflect.Field;
public class StaticInitReference {
 public static void main(String[] args) throws Exception {
  Class<?> c=Class.forName("net.minecraft.world.level.biome.BiomeManager");
  String[] names={"CHUNK_CENTER_QUART","ZOOM_BITS","ZOOM","ZOOM_MASK"};
  Field[] f=new Field[names.length];for(int i=0;i<f.length;i++){f[i]=c.getDeclaredField(names[i]);f[i].setAccessible(true);}
  for(String a:args)System.out.println(f[Integer.parseInt(a)].getInt(null));
 }
}
