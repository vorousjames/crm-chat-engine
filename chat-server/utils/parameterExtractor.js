const logger = require("./logger");

/**
 * Extracts action parameters from user's natural language message
 * Uses the inference service to parse the message and extract structured data
 */
class ParameterExtractor {
  constructor(inferenceService) {
    this.inferenceService = inferenceService;
  }

  /**
   * Extract parameters from a message based on the feature's request schema
   * @param {string} message - User's message
   * @param {Object} feature - Feature metadata including requestSchema
   * @returns {Object} - { parameters: {...}, missingRequired: [...], confidence: 0-1 }
   */
  async extractParameters(message, feature) {
    try {
      const requestSchema = JSON.parse(feature.requestSchema || "{}");
      
      if (!requestSchema.properties) {
        logger.warn("No schema properties to extract", { 
          featureType: feature.featureType 
        });
        return {
          parameters: {},
          missingRequired: [],
          confidence: 0,
          needsMoreInfo: false
        };
      }

      // Build extraction prompt for the LLM
      const extractionPrompt = this.buildExtractionPrompt(
        message, 
        requestSchema,
        feature
      );

      // Use inference service to extract parameters
      const response = await this.inferenceService.generateResponse({
        message: extractionPrompt,
        context: "",
        maxLength: 200
      });

      // Parse the LLM response to extract structured parameters
      const extracted = this.parseExtractionResponse(
        response.response,
        requestSchema
      );

      // Validate against schema
      const validation = this.validateParameters(
        extracted.parameters,
        requestSchema
      );

      logger.info("Parameter extraction complete", {
        featureType: feature.featureType,
        extractedCount: Object.keys(extracted.parameters).length,
        missingRequired: validation.missingRequired.length,
        confidence: extracted.confidence
      });

      return {
        parameters: extracted.parameters,
        missingRequired: validation.missingRequired,
        confidence: extracted.confidence,
        needsMoreInfo: validation.missingRequired.length > 0,
        validationErrors: validation.errors
      };

    } catch (error) {
      logger.error("Parameter extraction failed", {
        error: error.message,
        featureType: feature.featureType
      });
      
      return {
        parameters: {},
        missingRequired: [],
        confidence: 0,
        needsMoreInfo: true,
        error: error.message
      };
    }
  }

  /**
   * Build a prompt for the LLM to extract parameters
   */
  buildExtractionPrompt(message, schema, feature) {
    const properties = schema.properties || {};
    const required = schema.required || [];

    let prompt = `Extract the following information from the user's message. Return ONLY a JSON object with the extracted values, no other text.

User's message: "${message}"

Extract these fields:
`;

    Object.entries(properties).forEach(([fieldName, fieldSchema]) => {
      const isRequired = required.includes(fieldName);
      const type = fieldSchema.type || "string";
      const description = fieldSchema.description || "";
      
      prompt += `- ${fieldName} (${type}${isRequired ? ", REQUIRED" : ", optional"}): ${description}\n`;
    });

    prompt += `
If a field is not mentioned in the message, omit it from the JSON.
Return format: {"fieldName": "value", ...}

JSON response:`;

    return prompt;
  }

  /**
   * Parse the LLM's response to extract structured parameters
   */
  parseExtractionResponse(response, schema) {
    try {
      // Try to find JSON in the response
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      
      if (!jsonMatch) {
        logger.warn("No JSON found in extraction response", { response });
        return {
          parameters: {},
          confidence: 0.3
        };
      }

      const extracted = JSON.parse(jsonMatch[0]);
      
      // Calculate confidence based on how many fields were extracted
      const properties = schema.properties || {};
      const required = schema.required || [];
      const extractedCount = Object.keys(extracted).length;
      const requiredCount = required.length;
      const totalCount = Object.keys(properties).length;
      
      let confidence = 0.5; // base confidence
      
      if (requiredCount > 0) {
        const requiredExtracted = required.filter(r => extracted[r] !== undefined).length;
        confidence = requiredExtracted / requiredCount;
      } else if (totalCount > 0) {
        confidence = Math.min(extractedCount / totalCount, 1.0);
      }

      return {
        parameters: extracted,
        confidence: Math.max(confidence, 0.5) // Minimum 0.5 if we got valid JSON
      };

    } catch (error) {
      logger.error("Failed to parse extraction response", {
        error: error.message,
        response
      });
      
      return {
        parameters: {},
        confidence: 0.2
      };
    }
  }

  /**
   * Validate extracted parameters against schema
   */
  validateParameters(parameters, schema) {
    const required = schema.required || [];
    const properties = schema.properties || {};
    const errors = [];
    const missingRequired = [];

    // Check required fields
    required.forEach(fieldName => {
      if (parameters[fieldName] === undefined || parameters[fieldName] === null || parameters[fieldName] === "") {
        missingRequired.push({
          field: fieldName,
          type: properties[fieldName]?.type || "string",
          description: properties[fieldName]?.description || `The ${fieldName} field`
        });
      }
    });

    // Basic type validation
    Object.entries(parameters).forEach(([fieldName, value]) => {
      const fieldSchema = properties[fieldName];
      if (!fieldSchema) return;

      const expectedType = fieldSchema.type;
      const actualType = typeof value;

      // Simple type checking
      if (expectedType === "number" && actualType !== "number") {
        errors.push(`${fieldName} should be a number`);
      } else if (expectedType === "boolean" && actualType !== "boolean") {
        errors.push(`${fieldName} should be a boolean`);
      } else if (expectedType === "string" && actualType !== "string") {
        errors.push(`${fieldName} should be a string`);
      }

      // Email validation
      if (fieldSchema.format === "email" && actualType === "string") {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
          errors.push(`${fieldName} should be a valid email address`);
        }
      }
    });

    return {
      isValid: missingRequired.length === 0 && errors.length === 0,
      missingRequired,
      errors
    };
  }

  /**
   * Generate a user-friendly prompt to collect missing parameters
   */
  generateCollectionPrompt(missingRequired, feature) {
    if (missingRequired.length === 0) {
      return null;
    }

    const fieldsList = missingRequired.map(field => {
      return `• **${field.field}**: ${field.description}`;
    }).join('\n');

    return `To ${feature.featureDescription.toLowerCase()}, I need the following information:\n\n${fieldsList}\n\nPlease provide these details.`;
  }
}

module.exports = ParameterExtractor;
