const logger = require("../utils/logger");

function validateApiKey(req, res, next) {
  // Skip validation in development
  if (process.env.NODE_ENV === "development" && !process.env.API_KEY) {
    return next();
  }

  const apiKey =
    req.headers["x-api-key"] ||
    req.headers["authorization"]?.replace("Bearer ", "");

  if (!apiKey) {
    return res.status(401).json({
      error: "API key required",
      message: "Include X-API-Key header or Authorization: Bearer <key>",
    });
  }

  if (apiKey !== process.env.API_KEY) {
    logger.warn("Invalid API key attempt", {
      ip: req.ip,
      providedKey: apiKey.substring(0, 8) + "...",
    });

    return res.status(401).json({
      error: "Invalid API key",
    });
  }

  next();
}

module.exports = { validateApiKey };
