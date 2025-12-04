const express = require("express");
const Joi = require("joi");
const router = express.Router();

const WeaviateService = require("../utils/weaviateService");
const InferenceService = require("../utils/inferenceService");
const ParameterExtractor = require("../utils/parameterExtractor");
const logger = require("../utils/logger");
const { validateApiKey } = require("../middleware/auth");

// Initialize services lazily to handle connection errors gracefully
let weaviateService = null;
let inferenceService = null;
let parameterExtractor = null;

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

function getParameterExtractor() {
  if (!parameterExtractor) {
    const inferenceServiceInstance = getInferenceService();
    parameterExtractor = new ParameterExtractor(inferenceServiceInstance);
    logger.info("ParameterExtractor initialized successfully");
  }
  return parameterExtractor;
}

// Request validation schemas
const chatRequestSchema = Joi.object({
  message: Joi.string().required().min(1).max(1000).trim(),
  conversationId: Joi.string().optional().uuid(),
  userId: Joi.string().optional().alphanum().max(50),
  maxResults: Joi.number().optional().min(1).max(10).default(5),
  context: Joi.object().optional(), // User context for agent mode (permissions, auth, etc.)
});

// Main chat endpoint - mode determined by query param
router.post("/ask", validateApiKey, async (req, res, next) => {
  try {
    const startTime = Date.now();

    // Get mode from query parameter (defaults to 'ask' if not specified)
    const mode = req.query.mode === "agent" ? "agent" : "ask";

    // Validate request body
    const { error, value } = chatRequestSchema.validate(req.body);
    if (error) {
      return res.status(400).json({
        error: "Invalid request",
        details: error.details[0].message,
      });
    }

    const { message, conversationId, userId, maxResults, context } = value;

    logger.info("Processing chat request", {
      message: message.substring(0, 100),
      mode,
      conversationId,
      userId,
      requestId: req.id,
    });

    // Step 1: Search for relevant workflows
    logger.debug("Searching for relevant workflows...");
    const weaviateServiceInstance = getWeaviateService();
    const relevantWorkflows = await weaviateServiceInstance.searchFeatures(
      message,
      maxResults,
      true // Only return actionable features for agent mode
    );

    if (!relevantWorkflows || relevantWorkflows.length === 0) {
      logger.warn("No relevant workflows found", { message });
      return res.json({
        mode,
        response:
          "I'd be happy to help! However, I couldn't find specific information about that feature. You can ask about things like: getting estimates, managing leads, checking service areas, or using the admin dashboard. What would you like to know about?",
        confidence: 0.1,
        sources: [],
        processingTime: Date.now() - startTime,
      });
    }

    // Step 2: Route based on mode from query parameter
    if (mode === "agent") {
      return handleAgentMode(
        message,
        relevantWorkflows,
        context,
        conversationId,
        startTime,
        res,
        next
      );
    } else {
      return handleAskMode(
        message,
        relevantWorkflows,
        conversationId,
        startTime,
        res,
        next
      );
    }
  } catch (error) {
    logger.error("Chat request failed", {
      error: error.message,
      stack: error.stack,
    });
    next(error);
  }
});

// Agent mode handler - identifies actionable features
async function handleAgentMode(
  message,
  relevantWorkflows,
  context,
  conversationId,
  startTime,
  res,
  next
) {
  try {
    // Filter for agent-capable features
    const agentFeatures = relevantWorkflows.filter(
      (workflow) => workflow.isActionable === true
    );

    if (agentFeatures.length === 0) {
      logger.info(
        "No agent-capable features found, providing informational response"
      );
      return res.json({
        mode: "agent",
        detectedIntent: "no_action_available",
        confidence: 0.5,
        message:
          "I understand you want to perform an action, but this feature doesn't support automated execution yet. Let me explain how to do it manually.",
        fallbackToAsk: true,
        askModeResponse: await generateAskResponse(
          message,
          relevantWorkflows,
          conversationId
        ),
        processingTime: Date.now() - startTime,
      });
    }

    // Get the best matching agent feature (highest score)
    const bestFeature = agentFeatures[0];

    logger.info("Agent feature identified", {
      featureType: bestFeature.featureType,
      safetyLevel: bestFeature.safetyLevel,
      requiresConfirmation: bestFeature.requiresConfirmation,
    });

    // Extract parameters from the user's message
    const parameterExtractorInstance = getParameterExtractor();
    const extraction = await parameterExtractorInstance.extractParameters(
      message,
      bestFeature
    );

    logger.info("Parameter extraction complete", {
      parametersExtracted: Object.keys(extraction.parameters).length,
      missingRequired: extraction.missingRequired.length,
      confidence: extraction.confidence,
    });

    // Determine next step based on extraction results
    let nextStep = "ready_to_execute";
    let userMessage = generateAgentMessage(bestFeature);

    if (extraction.needsMoreInfo) {
      nextStep = "parameter_collection";
      userMessage =
        parameterExtractorInstance.generateCollectionPrompt(
          extraction.missingRequired,
          bestFeature
        ) || userMessage;
    } else if (bestFeature.requiresConfirmation) {
      nextStep = "confirmation_required";
      userMessage = `I can ${bestFeature.featureDescription.toLowerCase()} with the following details:\n\n${formatParametersForConfirmation(
        extraction.parameters
      )}\n\nWould you like me to proceed?`;
    }

    // Return agent action info with extracted parameters
    return res.json({
      mode: "agent",
      detectedIntent: "action_available",
      confidence: bestFeature.score || 0.85,
      feature: {
        type: bestFeature.featureType,
        description: bestFeature.featureDescription,
        canExecute: true,
        requiresConfirmation: bestFeature.requiresConfirmation,
        requiredPermissions: bestFeature.requiredPermissions,
        safetyLevel: bestFeature.safetyLevel,
        apiEndpoint: bestFeature.apiEndpoint,
        httpMethod: bestFeature.httpMethod,
        requestSchema: bestFeature.requestSchema,
        responseSchema: bestFeature.responseSchema,
        errorScenarios: bestFeature.errorScenarios,
        successCriteria: bestFeature.successCriteria,
      },
      // Extracted parameters ready for client to use
      parameterExtraction: {
        parameters: extraction.parameters,
        missingRequired: extraction.missingRequired,
        confidence: extraction.confidence,
        validationErrors: extraction.validationErrors || [],
      },
      message: userMessage,
      nextStep: nextStep,
      // Client-side execution instructions
      clientInstructions: {
        method:
          "Execute this action by making an API call with your user's authentication token",
        endpoint: bestFeature.apiEndpoint,
        httpMethod: bestFeature.httpMethod,
        body: extraction.parameters,
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer {USER_TOKEN}", // Client must provide user's token
        },
      },
      processingTime: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Agent mode handler failed", {
      error: error.message,
      stack: error.stack,
    });
    next(error);
  }
}

// Ask mode handler - provides informational responses
async function handleAskMode(
  message,
  relevantWorkflows,
  conversationId,
  startTime,
  res,
  next
) {
  try {
    // Build user-focused context for AI
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

    // Generate AI response
    logger.debug("Generating AI response...");
    const inferenceServiceInstance = getInferenceService();
    const aiResponse = await inferenceServiceInstance.generateResponse({
      message,
      context: contextText,
      conversationId,
    });

    // Format response
    const response = {
      mode: "ask",
      response: aiResponse.response,
      confidence: aiResponse.confidence || 0.8,
      sources: relevantWorkflows.map((workflow) => ({
        type: workflow.featureType,
        description: workflow.featureDescription,
        userType: workflow.userType,
        workflow: workflow.actualWorkflow,
        relevanceScore: workflow.score || 0.8,
        supportedModes: workflow.supportedModes,
      })),
      conversationId: conversationId || generateConversationId(),
      processingTime: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    };

    logger.info("Chat request completed (ask mode)", {
      processingTime: response.processingTime,
      confidence: response.confidence,
      workflowsFound: response.sources.length,
    });

    res.json(response);
  } catch (error) {
    logger.error("Ask mode handler failed", {
      error: error.message,
      stack: error.stack,
    });
    next(error);
  }
}

// Helper to generate agent-appropriate message
function generateAgentMessage(feature) {
  const action = feature.featureDescription.toLowerCase();

  if (feature.requiresConfirmation) {
    return `I can help you ${action}. This is a ${feature.safetyLevel} action that requires confirmation. Would you like me to proceed?`;
  }

  return `I can help you ${action}. What information do you need to provide?`;
}

// Helper to format parameters for confirmation
function formatParametersForConfirmation(parameters) {
  return Object.entries(parameters)
    .map(([key, value]) => `• **${key}**: ${value}`)
    .join("\n");
}

// Helper to generate ask mode response (for agent fallback)
async function generateAskResponse(message, workflows, conversationId) {
  const inferenceServiceInstance = getInferenceService();

  let contextText = "Here's how to do this:\n\n";
  workflows.forEach((workflow, index) => {
    contextText += `${index + 1}. ${workflow.featureDescription}\n`;
    contextText += `   Steps: ${workflow.userActions}\n\n`;
  });

  const aiResponse = await inferenceServiceInstance.generateResponse({
    message,
    context: contextText,
    conversationId,
  });

  return aiResponse.response;
}

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

// Health check endpoint to test Weaviate connection and service status
router.get("/health", validateApiKey, async (req, res, next) => {
  try {
    const startTime = Date.now();
    const weaviateServiceInstance = getWeaviateService();
    const inferenceServiceInstance = getInferenceService();

    // Test Weaviate connection
    const weaviateConnected = await weaviateServiceInstance.testConnection();

    // Test a simple search to verify indexing
    let featuresIndexed = false;
    let featureCount = 0;
    if (weaviateConnected) {
      try {
        const testResult = await weaviateServiceInstance.searchFeatures(
          "test",
          1
        );
        featuresIndexed = testResult.length > 0;
        featureCount = testResult.length;
      } catch (error) {
        logger.warn("Health check: feature search failed", {
          error: error.message,
        });
      }
    }

    // Check embedding model status
    const embeddingModelReady = weaviateServiceInstance.embeddingModelReady;

    const responseTime = Date.now() - startTime;
    const allHealthy =
      weaviateConnected && featuresIndexed && embeddingModelReady;

    res.status(allHealthy ? 200 : 503).json({
      status: allHealthy ? "healthy" : "degraded",
      services: {
        weaviate: {
          connected: weaviateConnected,
          features_indexed: featuresIndexed,
          feature_count: featureCount,
          status: weaviateConnected ? "operational" : "unavailable",
        },
        embedding_model: {
          ready: embeddingModelReady,
          status: embeddingModelReady ? "operational" : "loading",
        },
        inference: {
          available: inferenceServiceInstance !== null,
          status: "operational",
        },
      },
      environment: process.env.NODE_ENV || "development",
      responseTime: `${responseTime}ms`,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    logger.error("Health check failed", { error: error.message });
    res.status(503).json({
      status: "unhealthy",
      error: error.message,
      services: {
        weaviate: { connected: false, status: "error" },
        embedding_model: { ready: false, status: "error" },
        inference: { available: false, status: "error" },
      },
      timestamp: new Date().toISOString(),
    });
  }
});

// Helper function to generate conversation ID
function generateConversationId() {
  return "conv_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
}

module.exports = router;
