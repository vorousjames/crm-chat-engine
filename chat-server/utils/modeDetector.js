const logger = require("./logger");

/**
 * Detects whether a user query should be handled in ASK or AGENT mode
 * ASK mode: Informational queries ("How do I...?", "What is...?")
 * AGENT mode: Action requests ("Create a...", "Update...", "Send...")
 */
class ModeDetector {
  constructor() {
    // Action verbs that typically indicate agent mode
    this.actionVerbs = [
      "create",
      "add",
      "make",
      "new",
      "update",
      "edit",
      "change",
      "modify",
      "delete",
      "remove",
      "cancel",
      "send",
      "email",
      "schedule",
      "book",
      "set",
      "assign",
      "mark",
      "complete",
      "close",
      "open",
      "start",
      "begin",
      "submit",
      "save",
      "record",
      "log",
      "track",
    ];

    // Question words that typically indicate ask mode
    this.questionWords = [
      "how",
      "what",
      "why",
      "when",
      "where",
      "who",
      "which",
      "can",
      "could",
      "would",
      "should",
      "is",
      "are",
      "do",
      "does",
      "tell",
      "explain",
      "show",
      "describe",
    ];

    // Patterns that suggest specific data (indicating agent intent)
    this.specificDataPatterns = {
      email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/,
      phone: /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/,
      date: /\b(today|tomorrow|next week|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}\/\d{1,2}\/\d{2,4})\b/i,
      time: /\b\d{1,2}:\d{2}\s?(am|pm|AM|PM)?\b/,
      money: /\$\d+(\.\d{2})?|\d+\s?(dollars|usd)/i,
      name: /(for|to|from)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)/,
    };
  }

  /**
   * Main detection method
   * @param {string} message - User's message
   * @param {Array} searchResults - Results from Weaviate search
   * @param {string} explicitMode - Explicitly set mode from client (takes precedence)
   * @returns {Object} - { mode: 'ask'|'agent', confidence: number, reason: string }
   */
  detectMode(message, searchResults = [], explicitMode = null) {
    // If client explicitly sets mode, use it
    if (explicitMode === "ask" || explicitMode === "agent") {
      logger.debug("Using explicit mode from client", { mode: explicitMode });
      return {
        mode: explicitMode,
        confidence: 1.0,
        reason: "Explicitly set by client",
      };
    }

    const messageLower = message.toLowerCase().trim();
    let agentScore = 0;
    let askScore = 0;
    const reasons = [];

    // 1. Check for action verbs (strong indicator of agent mode)
    const hasActionVerb = this.actionVerbs.some((verb) =>
      messageLower.includes(verb)
    );
    if (hasActionVerb) {
      agentScore += 3;
      reasons.push("Contains action verb");
    }

    // 2. Check for question words (strong indicator of ask mode)
    const hasQuestionWord = this.questionWords.some((word) =>
      messageLower.startsWith(word)
    );
    if (hasQuestionWord) {
      askScore += 3;
      reasons.push("Starts with question word");
    }

    // 3. Check for question mark (indicates ask mode)
    if (messageLower.includes("?")) {
      askScore += 2;
      reasons.push("Contains question mark");
    }

    // 4. Check for specific data (indicates agent mode)
    const hasSpecificData = this.detectSpecificData(messageLower);
    if (hasSpecificData.found) {
      agentScore += 2;
      reasons.push(
        `Contains specific data: ${hasSpecificData.types.join(", ")}`
      );
    }

    // 5. Check if search results support agent mode
    const agentCapableResults = searchResults.filter((result) => {
      try {
        const supportedModes = JSON.parse(result.supportedModes || "[]");
        return result.canExecuteAction && supportedModes.includes("agent");
      } catch {
        return false;
      }
    });

    if (agentCapableResults.length > 0) {
      agentScore += 2;
      reasons.push(
        `${agentCapableResults.length} agent-capable features found`
      );
    } else if (searchResults.length > 0) {
      // If we have results but none are agent-capable, default to ask
      askScore += 2;
      reasons.push("No agent-capable features available");
    }

    // 6. Check for imperative tone (commands)
    const isImperative = this.detectImperativeTone(messageLower);
    if (isImperative) {
      agentScore += 2;
      reasons.push("Imperative tone detected");
    }

    // 7. Check for "help me" or "how to" phrases (ask mode)
    if (
      messageLower.includes("help me") ||
      messageLower.includes("how to") ||
      messageLower.includes("how do i") ||
      messageLower.includes("how can i")
    ) {
      askScore += 3;
      reasons.push("Help-seeking language detected");
    }

    // Calculate confidence based on score difference
    const totalScore = agentScore + askScore;
    const scoreDifference = Math.abs(agentScore - askScore);
    const confidence =
      totalScore > 0 ? Math.min(scoreDifference / totalScore, 1.0) : 0.5;

    // Determine mode
    const mode = agentScore > askScore ? "agent" : "ask";

    logger.debug("Mode detection complete", {
      message: message.substring(0, 50),
      mode,
      confidence,
      agentScore,
      askScore,
      reasons,
    });

    return {
      mode,
      confidence,
      reason: reasons.join("; "),
      agentScore,
      askScore,
    };
  }

  /**
   * Detect if message contains specific data (names, emails, dates, etc.)
   */
  detectSpecificData(message) {
    const foundTypes = [];

    for (const [type, pattern] of Object.entries(this.specificDataPatterns)) {
      if (pattern.test(message)) {
        foundTypes.push(type);
      }
    }

    return {
      found: foundTypes.length > 0,
      types: foundTypes,
    };
  }

  /**
   * Detect imperative tone (commands without question words)
   */
  detectImperativeTone(message) {
    // Remove common politeness words
    const cleanMessage = message
      .replace(/\b(please|kindly|could you|would you|can you)\b/gi, "")
      .trim();

    // If starts with action verb and no question words, likely imperative
    const startsWithAction = this.actionVerbs.some(
      (verb) =>
        cleanMessage.startsWith(verb) || cleanMessage.startsWith(`${verb} `)
    );

    const hasQuestionWord = this.questionWords.some((word) =>
      cleanMessage.includes(word)
    );

    return startsWithAction && !hasQuestionWord;
  }

  /**
   * Check if a specific feature supports agent mode
   */
  featureSupportsAgentMode(feature) {
    if (!feature) return false;

    try {
      const supportedModes = JSON.parse(feature.supportedModes || "[]");
      return feature.canExecuteAction && supportedModes.includes("agent");
    } catch (error) {
      logger.error("Error checking feature agent support", {
        error: error.message,
      });
      return false;
    }
  }

  /**
   * Get the best agent-capable feature from search results
   */
  getBestAgentFeature(searchResults) {
    const agentFeatures = searchResults.filter((result) =>
      this.featureSupportsAgentMode(result)
    );

    if (agentFeatures.length === 0) return null;

    // Return the highest scoring agent-capable feature
    return agentFeatures.reduce((best, current) => {
      return (current.score || 0) > (best.score || 0) ? current : best;
    }, agentFeatures[0]);
  }
}

module.exports = ModeDetector;
