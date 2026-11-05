import java.nio.file.Path;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configuration;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
import java.nio.charset.StandardCharsets;

/** Ejecuta Eula.class oficial y captura eventos del proveedor Log4j real. */
public class EulaLogOracle {
  static String hex(String s){return java.util.HexFormat.of().formatHex(s.getBytes(StandardCharsets.UTF_8));}
  static final class Capture extends AbstractAppender {
    final StringBuilder output=new StringBuilder();
    Capture(){super("capture",null,null,true,Property.EMPTY_ARRAY);}
    public void append(LogEvent e){output.append(e.getLevel()).append('|').append(hex(e.getLoggerName())).append('|').append(hex(e.getMessage().getFormattedMessage())).append('\n');}
  }
  public static void main(String[] args){
    LoggerContext ctx=(LoggerContext)org.apache.logging.log4j.LogManager.getContext(false);
    Configuration conf=ctx.getConfiguration();LoggerConfig root=conf.getRootLogger();
    for(String name:root.getAppenders().keySet())root.removeAppender(name);
    Capture capture=new Capture();capture.start();root.addAppender(capture,null,null);
    root.setLevel(org.apache.logging.log4j.Level.INFO);ctx.updateLoggers();
    net.minecraft.server.Eula eula=new net.minecraft.server.Eula(Path.of("eula.txt"));
    System.out.println(eula.hasAgreedToEULA());System.err.print(capture.output);ctx.stop();
  }
}
