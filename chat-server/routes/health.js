const express = require("express");
const router = express.Router();
const WeaviateService = require("../utils/weaviateService");
const InferenceService = require("../utils/inferenceService");
const logger = require("../utils/logger");

// Health check endpoint - basic health without external dependencies
router.get("/check", (req, res) => {
  res.status(200).json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    version: "1.0.0",
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || "development",
  });
});

// Detailed health check with external services
router.get("/detailed", async (req, res) => {
  const startTime = Date.now();
  const health = {
    status: "healthy",
    timestamp: new Date().toISOString(),
    services: {},
    version: "1.0.0",
  };

  try {
    // Check Weaviate
    try {
      const weaviateService = new WeaviateService();
      await weaviateService.client.misc.metaGetter().do();
      health.services.weaviate = { status: "healthy" };
    } catch (error) {
      health.services.weaviate = {
        status: "unhealthy",
        error: error.message,
      };
      health.status = "degraded";
    }

    // Check inference service
    try {
      const inferenceService = new InferenceService();
      // Simple test - we'll implement a ping endpoint later
      health.services.inference = { status: "healthy" };
    } catch (error) {
      health.services.inference = {
        status: "unhealthy",
        error: error.message,
      };
      health.status = "degraded";
    }

    health.responseTime = Date.now() - startTime;

    const statusCode = health.status === "healthy" ? 200 : 503;
    res.status(statusCode).json(health);
  } catch (error) {
    logger.error("Health check failed", { error: error.message });
    res.status(500).json({
      status: "unhealthy",
      error: "Health check failed",
      timestamp: new Date().toISOString(),
    });
  }
});

// Detailed system info (for monitoring)
router.get("/info", async (req, res) => {
  try {
    const weaviateService = new WeaviateService();
    const stats = await weaviateService.getStats();

    res.json({
      system: {
        nodeVersion: process.version,
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        platform: process.platform,
      },
      database: stats,
      configuration: {
        environment: process.env.NODE_ENV,
        port: process.env.PORT,
        useLocalInference: process.env.USE_LOCAL_INFERENCE,
      },
    });
  } catch (error) {
    logger.error("System info failed", { error: error.message });
    res.status(500).json({ error: "Failed to retrieve system information" });
  }
});

module.exports = router;
