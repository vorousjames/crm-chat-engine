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

      if (this.useLocalInference) {
        return await this.generateLocalResponse({ message: prompt, context });
      } else {
        return await this.generateRunpodResponse({ message: prompt, context });
      }
    } catch (error) {
      logger.error("Response generation failed", { error: error.message });

      // Return a proper fallback response structure
      return {
        response: this.generateFallbackResponse(message, context),
        confidence: 0.3,
        source: "fallback",
      };
    }
  }

  async generateLocalResponse({ message, context }) {
    try {
      const response = await axios.post(this.localUrl + "/generate", {
        prompt: message,
        max_length: 400,
        temperature: 0.3,
      });

      return {
        response:
          response.data?.generated_text ||
          "I apologize, but I couldn't generate a proper response.",
        confidence: 0.8,
        source: "local",
      };
    } catch (error) {
      logger.error("Local inference failed", { error: error.message });
      throw error;
    }
  }

  async generateRunpodResponse({ message, context }) {
    try {
      if (!this.runpodUrl || !this.runpodApiKey) {
        throw new Error("RunPod configuration missing");
      }

      const payload = {
        input: {
          message: message,
          max_length: 400,
          temperature: 0.3,
        },
      };

      logger.debug("Sending request to RunPod", {
        endpoint: this.runpodUrl,
        messageLength: message.length,
      });

      const response = await axios.post(this.runpodUrl, payload, {
        headers: {
          Authorization: `Bearer ${this.runpodApiKey}`,
          "Content-Type": "application/json",
        },
        timeout: 30000,
      });

      if (response.data?.status === "COMPLETED") {
        const generatedText =
          response.data?.output?.response ||
          response.data?.output?.generated_text ||
          "I couldn't generate a proper response.";

        return {
          response: generatedText,
          confidence: 0.9,
          source: "runpod",
        };
      } else {
        logger.warn("RunPod returned non-completed status", {
          status: response.data?.status,
        });
        throw new Error(`RunPod status: ${response.data?.status}`);
      }
    } catch (error) {
      logger.error("RunPod inference failed", { error: error.message });
      throw error;
    }
  }

  formatContextForAI(context) {
    if (!context || context.length === 0) {
      return "No specific context available.";
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

    // Simple keyword-based responses for your CRM
    if (
      lowerMessage.includes("login") ||
      lowerMessage.includes("admin") ||
      lowerMessage.includes("dashboard")
    ) {
      return `To access the admin dashboard, you'll need to navigate to the login page and enter your administrator credentials. Once logged in, you'll have access to the main dashboard where you can manage leads, users, and create marketing pages. If you don't have admin access, contact your system administrator.`;
    }

    if (lowerMessage.includes("estimate") || lowerMessage.includes("quote")) {
      return `To get an estimate, visit one of our service pages (like stamped concrete or demolition), click the "Get Free Estimate" button, fill out the form with your name, phone, address, and service type, then submit it. Our team will call you back within 24 hours to discuss your project.`;
    }

    if (lowerMessage.includes("lead") || lowerMessage.includes("customer")) {
      return `To manage leads, access the admin dashboard and click on the Leads tab. From there you can view all customer inquiries, update lead stages, add notes, and track your sales pipeline from initial contact to completed projects.`;
    }

    if (
      lowerMessage.includes("area") ||
      lowerMessage.includes("location") ||
      lowerMessage.includes("serve")
    ) {
      return `To check if we serve your area, visit our location-specific pages like /cleveland-ohio or /akron-ohio to see service availability in your city. You can also request an estimate and we'll confirm if we cover your location.`;
    }

    if (
      lowerMessage.includes("team") ||
      lowerMessage.includes("user") ||
      lowerMessage.includes("staff")
    ) {
      return `To manage team members, go to the admin dashboard and navigate to the Users tab. From there you can add new team members, set their roles and permissions, and track team activity.`;
    }

    // Generic helpful response
    return `I'd be happy to help you with "${message}"! This construction CRM system allows customers to request estimates through service pages, and staff to manage leads, users, and marketing pages through the admin dashboard. What specific feature would you like to know more about?`;
  }
}

module.exports = InferenceService;
