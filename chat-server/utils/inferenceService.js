const axios = require("axios");
const logger = require("./logger");

class InferenceService {
  constructor() {
    this.useLocalInference = process.env.USE_LOCAL_INFERENCE === "true";
    this.localUrl = process.env.LOCAL_INFERENCE_URL || "http://localhost:8000";
    this.runpodUrl = process.env.RUNPOD_ENDPOINT_URL;
    this.runpodApiKey = process.env.RUNPOD_API_KEY;
  }

  async generateResponse({ message, context, conversationId, userId }) {
    try {
      // Updated user-focused prompt
      const prompt = `You are a helpful assistant for a construction business CRM system. Your job is to help users understand what they can do in the application.

IMPORTANT GUIDELINES:
- Explain things from the user's perspective (what they see and do)
- Use simple, non-technical language
- Focus on step-by-step instructions for using the interface
- Don't mention code, functions, or technical implementation
- Be specific about buttons to click, forms to fill, and pages to visit
- Address the user directly with "you can" and "you should"

Context about available user workflows:
${context}

User's question: ${message}

Provide a helpful response that explains what the user can do in the interface:`;

      const payload = {
        input: {
          message: prompt,
          max_length: 400,
          temperature: 0.3,
        },
      };

      // ...rest of your existing RunPod API call code...
    } catch (error) {
      // ...existing error handling...
    }
  }

  async generateLocalResponse({ message, context }) {
    try {
      // This assumes your local inference server has an endpoint
      // You might need to adjust based on your actual implementation
      const payload = {
        input: {
          message,
          context: this.formatContextForAI(context),
          max_length: 400,
        },
      };

      logger.debug("Calling local inference service", {
        url: this.localUrl,
        messageLength: message.length,
        contextItems: context.length,
      });

      const response = await axios.post(`${this.localUrl}/inference`, payload, {
        timeout: 30000, // 30 second timeout
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (response.data.status === "success") {
        return {
          response: response.data.response,
          confidence: 0.8,
          source: "local",
          tokensUsed: response.data.tokens_used,
        };
      } else {
        throw new Error(response.data.error || "Local inference failed");
      }
    } catch (error) {
      logger.error("Local inference failed", { error: error.message });
      throw error;
    }
  }

  async generateRunpodResponse({ message, context }) {
    try {
      const payload = {
        input: {
          message,
          context: this.formatContextForAI(context),
          max_length: 400,
        },
      };

      logger.debug("Calling RunPod inference service", {
        endpoint: this.runpodUrl,
        messageLength: message.length,
        contextItems: context.length,
      });

      const response = await axios.post(this.runpodUrl, payload, {
        timeout: 60000, // 60 second timeout for RunPod
        headers: {
          Authorization: `Bearer ${this.runpodApiKey}`,
          "Content-Type": "application/json",
        },
      });

      if (response.data.status === "COMPLETED") {
        const output = response.data.output;
        return {
          response: output.response,
          confidence: 0.85,
          source: "runpod",
          tokensUsed: output.tokens_used,
          executionTime: response.data.executionTime,
        };
      } else {
        throw new Error("RunPod inference failed: " + response.data.error);
      }
    } catch (error) {
      logger.error("RunPod inference failed", { error: error.message });
      throw error;
    }
  }

  formatContextForAI(context) {
    if (!context || context.length === 0) {
      return "No specific features found, provide general help.";
    }

    return context
      .map(
        (feature, index) => `
Feature ${index + 1}: ${feature.description}
What it helps with: ${feature.benefit}
User actions: ${feature.actions}
Related features: ${feature.related}
---`
      )
      .join("\n");
  }

  generateFallbackResponse(message, context) {
    const lowerMessage = message.toLowerCase();

    // Simple keyword-based responses
    if (lowerMessage.includes("login") || lowerMessage.includes("sign in")) {
      return "To log into your account, look for a 'Login' or 'Sign In' button, usually found at the top of the page. You'll need your username/email and password.";
    }

    if (lowerMessage.includes("password")) {
      return "If you need to reset your password, look for a 'Forgot Password' link on the login page. You can also update your password in your account settings once logged in.";
    }

    if (lowerMessage.includes("search") || lowerMessage.includes("find")) {
      return "Most apps have a search feature - look for a search box (usually marked with a magnifying glass icon) where you can type keywords to find what you're looking for.";
    }

    if (lowerMessage.includes("export") || lowerMessage.includes("download")) {
      return "Many apps allow you to export or download your data. Look for 'Export', 'Download', or 'Save' options in menus or settings areas.";
    }

    if (lowerMessage.includes("edit") || lowerMessage.includes("update")) {
      return "To edit your information, look for 'Edit', 'Update', or pencil icons next to the information you want to change. Don't forget to save your changes!";
    }

    // Generic helpful response
    return `I'd be happy to help you with "${message}"! While I don't have specific information about this feature right now, I recommend checking the main menu or settings area of the app. You can also try looking for help documentation or contact support if available.`;
  }
}

module.exports = InferenceService;
