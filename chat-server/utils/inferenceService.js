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
      // Calculate context size to determine if follow-ups are needed
      const contextSize = context.length;
      const workflowCount = (context.match(/\d+\./g) || []).length;
      const needsFollowUps = contextSize > 1000 || workflowCount > 2;

      // Updated user-focused prompt with length constraint
      const prompt = `You are a helpful assistant for a construction business CRM system. Your job is to help users understand what they can do in the application.

CRITICAL RESPONSE RULES:
- Keep your response to 250 characters or less
- Be concise and direct - get to the point immediately
- Explain things from the user's perspective (what they see and do)
- Use simple, non-technical language
- Focus on step-by-step instructions for using the interface
- Don't mention code, functions, or technical implementation
- Be specific about buttons to click, forms to fill, and pages to visit
- Address the user directly with "you can" and "you should"
${needsFollowUps ? '\n- Since there is extensive information available, provide a brief summary and note that more details are available' : ''}

Context about available user workflows:
${context}

User's question: ${message}

Provide a helpful, concise response (250 characters max) that explains what the user can do in the interface:`;

      if (this.useLocalInference) {
        return await this.generateLocalResponse({ message: prompt, context, needsFollowUps, workflowCount });
      } else {
        return await this.generateRunpodResponse({ message: prompt, context, needsFollowUps, workflowCount });
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

  async generateLocalResponse({ message, context, needsFollowUps, workflowCount }) {
    try {
      const response = await axios.post(this.localUrl + "/generate", {
        prompt: message,
        max_length: 300,
        temperature: 0.3,
      });

      let generatedText =
        response.data?.generated_text ||
        "I apologize, but I couldn't generate a proper response.";

      // Enforce 250 character limit
      if (generatedText.length > 250) {
        generatedText = generatedText.substring(0, 247) + "...";
      }

      // Generate follow-up questions if needed
      const followUpQuestions = needsFollowUps
        ? this.generateFollowUpQuestions(context, workflowCount)
        : [];

      return {
        response: generatedText,
        followUpQuestions: followUpQuestions,
        confidence: 0.8,
        source: "local",
      };
    } catch (error) {
      logger.error("Local inference failed", { error: error.message });
      throw error;
    }
  }

  async generateRunpodResponse({ message, context, needsFollowUps, workflowCount }) {
    try {
      if (!this.runpodUrl || !this.runpodApiKey) {
        throw new Error("RunPod configuration missing");
      }

      const payload = {
        input: {
          message: message,
          max_length: 300,
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
        let generatedText =
          response.data?.output?.response ||
          response.data?.output?.generated_text ||
          "I couldn't generate a proper response.";

        // Enforce 250 character limit
        if (generatedText.length > 250) {
          generatedText = generatedText.substring(0, 247) + "...";
        }

        // Generate follow-up questions if needed
        const followUpQuestions = needsFollowUps
          ? this.generateFollowUpQuestions(context, workflowCount)
          : [];

        return {
          response: generatedText,
          followUpQuestions: followUpQuestions,
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

  generateFollowUpQuestions(context, workflowCount) {
    const questions = [];

    // Extract key topics from context
    const topics = this.extractTopicsFromContext(context);

    // Generate 2-3 relevant follow-up questions
    if (topics.includes("estimate")) {
      questions.push("Would you like more details on creating or managing estimates?");
    }
    if (topics.includes("lead") || topics.includes("pipeline")) {
      questions.push("Do you want to know more about managing your sales pipeline?");
    }
    if (topics.includes("analytics") || topics.includes("reporting")) {
      questions.push("Would you like details on viewing analytics and reports?");
    }
    if (topics.includes("contract")) {
      questions.push("Do you need help with contract creation or management?");
    }
    if (topics.includes("page") || topics.includes("builder")) {
      questions.push("Would you like to learn more about creating marketing pages?");
    }
    if (topics.includes("user") || topics.includes("team")) {
      questions.push("Do you want to know more about managing team members and permissions?");
    }

    // Return 2-3 most relevant questions
    return questions.slice(0, 3);
  }

  extractTopicsFromContext(context) {
    const topics = [];
    const topicKeywords = {
      estimate: ["estimate", "quote", "pricing"],
      lead: ["lead", "customer", "inquiry"],
      analytics: ["analytics", "report", "metric", "kpi"],
      contract: ["contract", "agreement", "signing"],
      page: ["page", "builder", "marketing", "content"],
      user: ["user", "team", "permission", "role"],
    };

    const lowerContext = context.toLowerCase();
    for (const [topic, keywords] of Object.entries(topicKeywords)) {
      if (keywords.some((keyword) => lowerContext.includes(keyword))) {
        topics.push(topic);
      }
    }

    return topics;
  }

  generateFallbackResponse(message, context) {
    const lowerMessage = message.toLowerCase();

    // Simple keyword-based responses for your CRM (kept concise)
    if (
      lowerMessage.includes("login") ||
      lowerMessage.includes("admin") ||
      lowerMessage.includes("dashboard")
    ) {
      return `Access the admin dashboard via the login page. Once logged in, you can manage leads, users, and create marketing pages.`;
    }

    if (lowerMessage.includes("estimate") || lowerMessage.includes("quote")) {
      return `Visit a service page, click "Get Free Estimate", fill out the form, and submit. We'll call you within 24 hours.`;
    }

    if (lowerMessage.includes("lead") || lowerMessage.includes("customer")) {
      return `Go to the admin dashboard and click the Leads tab to view inquiries, update stages, add notes, and track your pipeline.`;
    }

    if (
      lowerMessage.includes("area") ||
      lowerMessage.includes("location") ||
      lowerMessage.includes("serve")
    ) {
      return `Check location pages like /cleveland-ohio or /akron-ohio to see service availability, or request an estimate to confirm coverage.`;
    }

    if (
      lowerMessage.includes("team") ||
      lowerMessage.includes("user") ||
      lowerMessage.includes("staff")
    ) {
      return `Go to the admin dashboard, navigate to the Users tab to add team members, set roles, and manage permissions.`;
    }

    // Generic helpful response (concise)
    return `I can help with estimates, lead management, analytics, contracts, and more. What would you like to know?`;
  }
}

module.exports = InferenceService;
