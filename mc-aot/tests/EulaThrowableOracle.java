import java.nio.file.Path;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
/** Registra Throwable asociado a eventos de Eula real, no sólo el mensaje. */
public class EulaThrowableOracle {
 static final class Capture extends AbstractAppender {
  final StringBuilder output=new StringBuilder();
  Capture(){super("capture",null,null,true,Property.EMPTY_ARRAY);}
  public void append(LogEvent e){Throwable t=e.getThrown();output.append(e.getLevel()).append('|').append(e.getLoggerName()).append('|').append(e.getMessage().getFormattedMessage()).append('|').append(t==null?"NO_THROWABLE":t.getClass().getName()).append('\n');}
 }
 public static void main(String[] a){
  LoggerContext ctx=(LoggerContext)org.apache.logging.log4j.LogManager.getContext(false);
  LoggerConfig root=ctx.getConfiguration().getRootLogger();
  for(String n:root.getAppenders().keySet())root.removeAppender(n);
  Capture c=new Capture();c.start();root.addAppender(c,null,null);root.setLevel(org.apache.logging.log4j.Level.INFO);ctx.updateLoggers();
  System.out.println(new net.minecraft.server.Eula(Path.of("eula.txt")).hasAgreedToEULA());
  System.err.print(c.output);ctx.stop();
 }
}
