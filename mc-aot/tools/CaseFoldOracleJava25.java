// Comprueba todas las parejas Latin-1 x BMP contra String.equalsIgnoreCase.
public class CaseFoldOracleJava25 {
 public static void main(String[] args) {
  if (Runtime.version().feature() != 25) throw new IllegalStateException("Se requiere Java 25");
  String[] chars=new String[65536];int[] folded=new int[65536];
  for (int i=0;i<65536;i++) {chars[i]=String.valueOf((char)i);folded[i]=Character.toLowerCase(Character.toUpperCase(i));}
  long n=0;
  for (int a=0;a<256;a++) for (int b=0;b<65536;b++) {
   boolean model=folded[a]==folded[b], actual=chars[a].equalsIgnoreCase(chars[b]);
   if (model!=actual) throw new AssertionError(String.format("mismatch %04x %04x %s %s",a,b,model,actual));n++;
  }
  System.out.println("OK: "+n+" parejas Latin-1 x BMP coinciden con Character simple de Java 25");
 }
}
