import java.nio.charset.StandardCharsets;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configuration;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** SLF4J+Log4j reales del bundle; configuración explícita para eventos normalizados. */
public class Log4rsOracle {
  static String hex(String s) { return java.util.HexFormat.of().formatHex(s.getBytes(StandardCharsets.UTF_8)); }
  static final class Capture extends AbstractAppender {
    final StringBuilder result=new StringBuilder();
    Capture(){super("capture",null,null,true,Property.EMPTY_ARRAY);}
    public void append(LogEvent e){result.append(e.getLevel()).append('|').append(hex(e.getLoggerName())).append('|').append(hex(e.getMessage().getFormattedMessage())).append('\n');}
  }
  public static void main(String[] args){
    LoggerContext ctx=(LoggerContext)org.apache.logging.log4j.LogManager.getContext(false);
    Configuration conf=ctx.getConfiguration(); LoggerConfig root=conf.getRootLogger();
    for(String name:root.getAppenders().keySet())root.removeAppender(name);
    Capture capture=new Capture();capture.start();root.addAppender(capture,null,null);
    root.setLevel(org.apache.logging.log4j.Level.valueOf(args[0]));ctx.updateLoggers();
    String[] names={"server","net.minecraft.server.Main","玩家.世界",""};
    String[] patterns={"Server starting","hello {}","{}|{}","none {} {} {}","こんにちは {}","","{}{}{}"};
    Object[][] arguments={{},{"Alex"},{"a",null},{"世界","x","extra"}};
    for(int i=0;i<5;i++)for(String name:names){
      Logger log=LoggerFactory.getLogger(name);
      boolean enabled=switch(i){case 0->log.isErrorEnabled();case 1->log.isWarnEnabled();case 2->log.isInfoEnabled();case 3->log.isDebugEnabled();default->log.isTraceEnabled();};
      String level=switch(i){case 0->"ERROR";case 1->"WARN";case 2->"INFO";case 3->"DEBUG";default->"TRACE";};
      System.out.println("enabled|"+level+"|"+name+"|"+enabled);
      for(String pattern:patterns)for(Object[] a:arguments){
        switch(i){case 0->log.error(pattern,a);case 1->log.warn(pattern,a);case 2->log.info(pattern,a);case 3->log.debug(pattern,a);default->log.trace(pattern,a);}
      }
    }
    System.err.print(capture.result.toString());ctx.stop();
  }
}
