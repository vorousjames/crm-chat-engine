const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
require("dotenv").config();

console.log("Loading routes and middleware...");

const chatRoutes = require("./routes/chat");
const healthRoutes = require("./routes/health");
const errorHandler = require("./middleware/errorHandler");
const logger = require("./utils/logger");

console.log("All modules loaded successfully");

const app = express();
const PORT = process.env.PORT || 3001;

// Security middleware
app.use(helmet());

// CORS configuration - allow all origins since we're using API key authentication
app.use(
  cors({
    origin: "*", // Explicitly allow all origins
    credentials: false, // Set to false when using origin: "*"
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization", "X-API-Key"],
    preflightContinue: false,
    optionsSuccessStatus: 200,
  })
);

// Explicit OPTIONS handler for all routes
app.options("*", cors());

// Body parsing middleware
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// Request logging
app.use((req, res, next) => {
  logger.info(`${req.method} ${req.path}`, {
    ip: req.ip,
    userAgent: req.get("User-Agent"),
    timestamp: new Date().toISOString(),
  });
  next();
});

// Routes
app.use("/api/chat", chatRoutes);
app.use("/api/health", healthRoutes);

// Wake endpoint for serverless cold start
app.get("/api/wake", (req, res) => {
  const startTime = Date.now();

  try {
    // Perform any necessary warm-up operations here
    // e.g., initialize connections, load models, etc.

    const responseTime = Date.now() - startTime;

    logger.info("Wake endpoint called", {
      responseTime: `${responseTime}ms`,
      timestamp: new Date().toISOString(),
    });

    res.json({
      status: "awake",
      message: "Chatbot has woken up",
      timestamp: new Date().toISOString(),
      responseTime: `${responseTime}ms`,
      environment: process.env.NODE_ENV || "development",
      version: "1.0.0",
    });
  } catch (error) {
    logger.error("Wake endpoint error", { error: error.message });
    res.status(503).json({
      status: "warming_up",
      message: "Chatbot is waking up, please retry in a moment",
      error: error.message,
    });
  }
});

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    service: "CRM Chatbot API",
    version: "1.0.0",
    status: "operational",
    endpoints: {
      chat: "/api/chat",
      health: "/api/health/check",
      wake: "/api/wake", // Add this line
    },
    documentation: "/api/docs",
  });
});

// 404 handler
app.use("*", (req, res) => {
  res.status(404).json({
    error: "Endpoint not found",
    message: `Cannot ${req.method} ${req.originalUrl}`,
    availableEndpoints: [
      "GET /",
      "POST /api/chat/ask",
      "GET /api/health/check",
      "GET /api/wake", // Add this line
    ],
  });
});

// Error handling middleware (must be last)
app.use(errorHandler);

// Graceful shutdown
process.on("SIGTERM", () => {
  logger.info("SIGTERM received, shutting down gracefully");
  process.exit(0);
});

process.on("SIGINT", () => {
  logger.info("SIGINT received, shutting down gracefully");
  process.exit(0);
});

// Start server with error handling
try {
  app.listen(PORT, () => {
    logger.info(`🚀 Home-Service Chatbot API running on port ${PORT}`);
    logger.info(`📍 Environment: ${process.env.NODE_ENV}`);
    logger.info(`🔗 Local access: http://localhost:${PORT}`);
    logger.info(`📚 API Documentation: http://localhost:${PORT}/api/docs`);
  });
} catch (error) {
  logger.error("Failed to start server", {
    error: error.message,
    stack: error.stack,
  });
  process.exit(1);
}

// Handle uncaught exceptions
process.on("uncaughtException", (error) => {
  logger.error("Uncaught Exception", {
    error: error.message,
    stack: error.stack,
  });
  process.exit(1);
});

process.on("unhandledRejection", (reason, promise) => {
  logger.error("Unhandled Rejection", { reason, promise });
  process.exit(1);
});

module.exports = app;
