const express = require("express");
const Joi = require("joi");
const router = express.Router();

const WeaviateService = require("../utils/weaviateService");
const InferenceService = require("../utils/inferenceService");
const logger = require("../utils/logger");
const { validateApiKey } = require("../middleware/auth");

// Initialize services lazily to handle connection errors gracefully
let weaviateService = null;
let inferenceService = null;

function getWeaviateService() {
  if (!weaviateService) {
    try {
      weaviateService = new WeaviateService();
      logger.info("WeaviateService initialized successfully");
    } catch (error) {
      logger.error("Failed to initialize WeaviateService", { error: error.message });
      throw new Error("Search service initialization failed");
    }
  }
  return weaviateService;
}

function getInferenceService() {
  if (!inferenceService) {
    try {
      inferenceService = new InferenceService();
      logger.info("InferenceService initialized successfully");
    } catch (error) {
      logger.error("Failed to initialize InferenceService", { error: error.message });
      throw new Error("AI service initialization failed");
    }
  }
  return inferenceService;
}

// Request validation schemas
const chatRequestSchema = Joi.object({
  message: Joi.string().required().min(1).max(1000).trim(),
  conversationId: Joi.string().optional().uuid(),
  userId: Joi.string().optional().alphanum().max(50),
  maxResults: Joi.number().optional().min(1).max(10).default(5),
});

// Main chat endpoint
router.post("/ask", validateApiKey, async (req, res, next) => {
  try {
    const startTime = Date.now();

    // Validate request
    const { error, value } = chatRequestSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        error: "Invalid request",
        details: error.details[0].message,
      });
    }

    const { message, conversationId, userId, maxResults } = value;

    logger.info("Processing chat request", {
      message: message.substring(0, 100),
      conversationId,
      userId,
      requestId: req.id,
    });

    // Step 1: Search for relevant app features
    logger.debug("Searching for relevant features...");
    const weaviateServiceInstance = getWeaviateService();
    const relevantFeatures = await weaviateServiceInstance.searchFeatures(
      message,
      maxResults
    );

    if (!relevantFeatures || relevantFeatures.length === 0) {
      logger.warn("No relevant features found", { message });
      return res.json({
        response:
          "I'd be happy to help! However, I couldn't find specific features related to your question. Could you try rephrasing or ask about a specific part of the app you're interested in?",
        confidence: 0.1,
        sources: [],
        processingTime: Date.now() - startTime,
      });
    }

    // Step 2: Prepare context for AI
    const context = relevantFeatures.map((feature) => ({
      description: feature.featureDescription,
      benefit: feature.userBenefit,
      actions: feature.userActions,
      related: feature.relatedFeatures,
    }));

    logger.debug(`Found ${relevantFeatures.length} relevant features`);

    // Step 3: Generate AI response
    logger.debug("Generating AI response...");
    const inferenceServiceInstance = getInferenceService();
    const aiResponse = await inferenceServiceInstance.generateResponse({
      message,
      context: context,
      conversationId,
      userId,
    });

    // Step 4: Format response
    const response = {
      response: aiResponse.response,
      confidence: aiResponse.confidence || 0.8,
      sources: relevantFeatures.map((feature) => ({
        type: feature.featureType,
        description: feature.featureDescription,
        relevanceScore: feature.score || 0.8,
      })),
      conversationId: conversationId || generateConversationId(),
      processingTime: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    };

    logger.info("Chat request completed", {
      processingTime: response.processingTime,
      confidence: response.confidence,
      sourcesFound: response.sources.length,
    });

    res.json(response);
  } catch (error) {
    logger.error("Chat request failed", {
      error: error.message,
      stack: error.stack,
    });
    next(error);
  }
});

// Get conversation history (if implementing conversation memory)
router.get(
  "/conversation/:conversationId",
  validateApiKey,
  async (req, res, next) => {
    try {
      const { conversationId } = req.params;

      // This would integrate with a conversation storage system
      // For now, return empty history
      res.json({
        conversationId,
        messages: [],
        createdAt: new Date().toISOString(),
        lastActivity: new Date().toISOString(),
      });
    } catch (error) {
      logger.error("Failed to retrieve conversation", { error: error.message });
      next(error);
    }
  }
);

// Get available feature types
router.get("/features/types", validateApiKey, async (req, res, next) => {
  try {
    const weaviateServiceInstance = getWeaviateService();
    const featureTypes = await weaviateServiceInstance.getFeatureTypes();

    res.json({
      featureTypes,
      total: featureTypes.length,
      examples: {
        authentication: "How do I log in?",
        data_management: "Can I edit my information?",
        search_filter: "How do I find something?",
        reporting: "Can I export my data?",
      },
    });
  } catch (error) {
    logger.error("Failed to get feature types", { error: error.message });
    next(error);
  }
});

// Suggest questions based on available features
router.get("/suggestions", validateApiKey, async (req, res, next) => {
  try {
    const weaviateServiceInstance = getWeaviateService();
    const suggestions = await weaviateServiceInstance.getSuggestedQuestions();

    res.json({
      suggestions: suggestions || [
        "How do I log into my account?",
        "Can I update my profile information?",
        "How do I search for information?",
        "Is there a way to export my data?",
        "What can I do on the main dashboard?",
      ],
      total: suggestions?.length || 5,
    });
  } catch (error) {
    logger.error("Failed to get suggestions", { error: error.message });
    next(error);
  }
});

// Helper function to generate conversation ID
function generateConversationId() {
  return "conv_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
}

module.exports = router;
