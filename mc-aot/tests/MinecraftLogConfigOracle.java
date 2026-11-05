import java.nio.charset.StandardCharsets;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.Marker;
import org.slf4j.MarkerFactory;
/** Carga XML real de Mojang, conserva filtro raíz y reemplaza sólo destinos con captura. */
public class MinecraftLogConfigOracle {
  static String hex(String s){return java.util.HexFormat.of().formatHex(s.getBytes(StandardCharsets.UTF_8));}
  static final class Capture extends AbstractAppender {
    final StringBuilder output=new StringBuilder();
    Capture(){super("capture",null,null,true,Property.EMPTY_ARRAY);}
    public void append(LogEvent e){output.append(e.getLevel()).append('|').append(hex(e.getLoggerName())).append('|').append(hex(e.getMessage().getFormattedMessage())).append('\n');}
  }
  public static void main(String[] args){
    LoggerContext ctx=(LoggerContext)org.apache.logging.log4j.LogManager.getContext(false);
    LoggerConfig root=ctx.getConfiguration().getRootLogger();
    for(String name:root.getAppenders().keySet())root.removeAppender(name);
    Capture c=new Capture();c.start();root.addAppender(c,null,null);ctx.updateLoggers();
    Logger log=LoggerFactory.getLogger("net.minecraft.test.MarkerProbe");
    Marker blocked=MarkerFactory.getMarker("NETWORK_PACKETS");
    Marker child=MarkerFactory.getMarker("INHERITS_NETWORK");child.add(blocked);
    Marker allowed=MarkerFactory.getMarker("OTHER");
    System.err.println("enabled|"+log.isInfoEnabled(blocked)+"|"+log.isInfoEnabled(child)+"|"+log.isInfoEnabled(allowed));
    log.debug("disabled-debug");log.info("unmarked");log.info(blocked,"blocked");log.info(child,"blocked-child");log.info(allowed,"allowed");log.warn("warning");
    System.out.print(c.output);ctx.stop();
  }
}
