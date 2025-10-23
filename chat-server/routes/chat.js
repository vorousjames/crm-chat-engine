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
      logger.error("Failed to initialize WeaviateService", {
        error: error.message,
      });
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
      logger.error("Failed to initialize InferenceService", {
        error: error.message,
      });
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

    // Step 1: Search for relevant user workflows
    logger.debug("Searching for relevant user workflows...");
    const weaviateServiceInstance = getWeaviateService();
    const relevantWorkflows = await weaviateServiceInstance.searchFeatures(
      message,
      maxResults
    );

    if (!relevantWorkflows || relevantWorkflows.length === 0) {
      logger.warn("No relevant workflows found", { message });
      return res.json({
        response:
          "I'd be happy to help! However, I couldn't find specific information about that feature. You can ask about things like: getting estimates, managing leads, checking service areas, or using the admin dashboard. What would you like to know about?",
        confidence: 0.1,
        sources: [],
        processingTime: Date.now() - startTime,
      });
    }

    // Step 2: Build user-focused context for AI
    let contextText = "Here's what users can do in the application:\n\n";

    relevantWorkflows.forEach((workflow, index) => {
      contextText += `${index + 1}. ${workflow.featureDescription}\n`;
      contextText += `   • User type: ${workflow.userType}\n`;
      contextText += `   • How to do it: ${workflow.userActions}\n`;
      contextText += `   • What you provide: ${workflow.inputs}\n`;
      contextText += `   • What you get: ${workflow.outputs}\n`;
      contextText += `   • Interface elements: ${workflow.uiComponents}\n`;
      contextText += `   • User benefit: ${workflow.userBenefit}\n\n`;
    });

    logger.debug(`Found ${relevantWorkflows.length} relevant workflows`);

    // Step 3: Generate AI response with user-focused prompt
    logger.debug("Generating AI response...");
    const inferenceServiceInstance = getInferenceService();
    const aiResponse = await inferenceServiceInstance.generateResponse({
      message,
      context: contextText,
      conversationId,
      userId,
    });

    // Step 4: Format response with workflow information
    const response = {
      response: aiResponse.response,
      confidence: aiResponse.confidence || 0.8,
      sources: relevantWorkflows.map((workflow) => ({
        type: workflow.featureType,
        description: workflow.featureDescription,
        userType: workflow.userType,
        workflow: workflow.actualWorkflow,
        relevanceScore: workflow.score || 0.8,
      })),
      conversationId: conversationId || generateConversationId(),
      processingTime: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    };

    logger.info("Chat request completed", {
      processingTime: response.processingTime,
      confidence: response.confidence,
      workflowsFound: response.sources.length,
      workflowTypes: response.sources.map((s) => s.type),
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

// Get available workflow types (updated for user workflows)
router.get("/features/types", validateApiKey, async (req, res, next) => {
  try {
    const weaviateServiceInstance = getWeaviateService();
    const workflowTypes = await weaviateServiceInstance.getFeatureTypes();

    res.json({
      workflowTypes,
      total: workflowTypes.length,
      examples: {
        customer_estimate_request:
          "How do I get an estimate for concrete work?",
        staff_lead_management: "How do I manage customer leads?",
        service_area_discovery: "Do you serve Cleveland?",
        staff_team_management: "How do I add team members?",
        marketing_page_creation: "How do I create marketing pages?",
      },
    });
  } catch (error) {
    logger.error("Failed to get workflow types", { error: error.message });
    next(error);
  }
});

// Suggest questions based on available user workflows
router.get("/suggestions", validateApiKey, async (req, res, next) => {
  try {
    const weaviateServiceInstance = getWeaviateService();
    const suggestions = await weaviateServiceInstance.getSuggestedQuestions();

    res.json({
      suggestions: suggestions || [
        "How do I get an estimate for concrete work?",
        "How do I request demolition services?",
        "How do I manage customer leads?",
        "Do you serve my area?",
        "How do I add new team members?",
        "How do I create marketing pages?",
        "How do I track project revenue?",
        "What can customers do on the website?",
      ],
      total: suggestions?.length || 8,
      categories: {
        "For Customers": [
          "How do I get an estimate?",
          "Do you serve my area?",
          "What services do you offer?",
        ],
        "For Staff": [
          "How do I manage leads?",
          "How do I add team members?",
          "How do I create marketing pages?",
        ],
      },
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
