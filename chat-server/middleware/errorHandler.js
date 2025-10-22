const logger = require("../utils/logger");

function errorHandler(err, req, res, next) {
  logger.error("Request failed", {
    error: err.message,
    stack: err.stack,
    method: req.method,
    url: req.url,
    ip: req.ip,
  });

  // Default error response
  let statusCode = 500;
  let message = "Internal server error";

  // Handle specific error types
  if (err.name === "ValidationError") {
    statusCode = 400;
    message = "Invalid request data";
  } else if (err.message.includes("Weaviate")) {
    statusCode = 503;
    message = "Search service temporarily unavailable";
  } else if (err.message.includes("timeout")) {
    statusCode = 504;
    message = "Request timeout - please try again";
  } else if (err.status) {
    statusCode = err.status;
    message = err.message;
  }

  res.status(statusCode).json({
    error: message,
    requestId: req.id || "unknown",
    timestamp: new Date().toISOString(),
  });
}

module.exports = errorHandler;
