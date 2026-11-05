// Regenera la tabla simple usada por equalsIgnoreCase de Java 25. No hace fold expansivo.
public class CaseFoldJava25 {
 public static void main(String[] args) {
  if (Runtime.version().feature() != 25) throw new IllegalStateException("Se requiere Java 25");
  for (int c=0;c<=Character.MAX_CODE_POINT;c++) {
   int upper=Character.toUpperCase(c), fold=Character.toLowerCase(upper);
   if (c!=fold) System.out.printf("%x %x%n",c,fold);
  }
 }
}
