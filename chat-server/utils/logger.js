const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

const currentLevel = logLevels[process.env.LOG_LEVEL] || logLevels.info;

class Logger {
  log(level, message, meta = {}) {
    if (logLevels[level] <= currentLevel) {
      const timestamp = new Date().toISOString();
      const logEntry = {
        timestamp,
        level: level.toUpperCase(),
        message,
        ...meta,
      };

      if (level === "error") {
        console.error(JSON.stringify(logEntry, null, 2));
      } else {
        console.log(JSON.stringify(logEntry, null, 2));
      }
    }
  }

  error(message, meta) {
    this.log("error", message, meta);
  }
  warn(message, meta) {
    this.log("warn", message, meta);
  }
  info(message, meta) {
    this.log("info", message, meta);
  }
  debug(message, meta) {
    this.log("debug", message, meta);
  }
}

module.exports = new Logger();
