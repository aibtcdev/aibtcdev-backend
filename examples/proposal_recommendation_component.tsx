/**
 * React component example for using the Proposal Recommendation API
 *
 * This demonstrates how to integrate the proposal recommendation API
 * into a React/Next.js frontend application.
 */

import React, { useState } from "react";
import type {
  ProposalRecommendationRequest,
  ProposalRecommendationResult,
  ProposalRecommendationResponse,
  ProposalPriority,
} from "./proposal_recommendation_types";
import {
  generateProposalRecommendation,
  isProposalRecommendationError,
  formatProposalRecommendation,
  validateRequest,
  extractMetrics,
} from "./proposal_recommendation_types";

// ============================================================================
// COMPONENT INTERFACES
// ============================================================================

interface ProposalRecommendationFormProps {
  /** Authentication token for API calls */
  authToken: string;

  /** Callback when a recommendation is generated */
  onRecommendationGenerated?: (
    recommendation: ProposalRecommendationResponse
  ) => void;

  /** Optional initial DAO ID */
  initialDaoId?: string;
}

interface FormData {
  daoId: string;
  focusArea: string;
  specificNeeds: string;
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const ProposalRecommendationForm: React.FC<
  ProposalRecommendationFormProps
> = ({ authToken, onRecommendationGenerated, initialDaoId = "" }) => {
  // Form state
  const [formData, setFormData] = useState<FormData>({
    daoId: initialDaoId,
    focusArea: "",
    specificNeeds: "",
  });

  // API state
  const [isLoading, setIsLoading] = useState(false);
  const [recommendation, setRecommendation] =
    useState<ProposalRecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Handle form input changes
  const handleInputChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setValidationErrors([]); // Clear validation errors when user types
    setError(null); // Clear API errors when user types
  };

  // Validate and submit form
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Create API request object
    const request: ProposalRecommendationRequest = {
      dao_id: formData.daoId,
      ...(formData.focusArea && { focus_area: formData.focusArea }),
      ...(formData.specificNeeds && { specific_needs: formData.specificNeeds }),
    };

    // Validate request
    const errors = validateRequest(request);
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }

    setIsLoading(true);
    setError(null);
    setValidationErrors([]);

    try {
      const result: ProposalRecommendationResult =
        await generateProposalRecommendation(request, authToken);

      if (isProposalRecommendationError(result)) {
        setError(result.error);
        setRecommendation(null);
      } else {
        setRecommendation(result);
        setError(null);
        onRecommendationGenerated?.(result);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(`Failed to generate recommendation: ${errorMessage}`);
      setRecommendation(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Reset form
  const handleReset = () => {
    setFormData({ daoId: initialDaoId, focusArea: "", specificNeeds: "" });
    setRecommendation(null);
    setError(null);
    setValidationErrors([]);
  };

  return (
    <div className="proposal-recommendation-form">
      <h2>Generate Proposal Recommendation</h2>

      {/* Form */}
      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label htmlFor="daoId">DAO ID *</label>
          <input
            id="daoId"
            type="text"
            value={formData.daoId}
            onChange={(e) => handleInputChange("daoId", e.target.value)}
            placeholder="12345678-1234-5678-9abc-123456789abc"
            disabled={isLoading}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="focusArea">Focus Area (Optional)</label>
          <select
            id="focusArea"
            value={formData.focusArea}
            onChange={(e) => handleInputChange("focusArea", e.target.value)}
            disabled={isLoading}
          >
            <option value="">Select focus area...</option>
            <option value="community growth">Community Growth</option>
            <option value="technical development">Technical Development</option>
            <option value="partnerships">Partnerships</option>
            <option value="governance">Governance</option>
            <option value="marketing">Marketing</option>
            <option value="treasury management">Treasury Management</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="specificNeeds">Specific Needs (Optional)</label>
          <textarea
            id="specificNeeds"
            value={formData.specificNeeds}
            onChange={(e) => handleInputChange("specificNeeds", e.target.value)}
            placeholder="Describe any specific needs or requirements..."
            rows={3}
            disabled={isLoading}
          />
        </div>

        {/* Validation Errors */}
        {validationErrors.length > 0 && (
          <div className="error-list">
            <strong>Please fix the following errors:</strong>
            <ul>
              {validationErrors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Form Actions */}
        <div className="form-actions">
          <button type="submit" disabled={isLoading}>
            {isLoading ? "Generating..." : "Generate Recommendation"}
          </button>
          <button type="button" onClick={handleReset} disabled={isLoading}>
            Reset
          </button>
        </div>
      </form>

      {/* Loading State */}
      {isLoading && (
        <div className="loading">
          <p>Analyzing DAO context and generating recommendation...</p>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Recommendation Results */}
      {recommendation && (
        <RecommendationDisplay recommendation={recommendation} />
      )}
    </div>
  );
};

// ============================================================================
// RECOMMENDATION DISPLAY COMPONENT
// ============================================================================

interface RecommendationDisplayProps {
  recommendation: ProposalRecommendationResponse;
}

const RecommendationDisplay: React.FC<RecommendationDisplayProps> = ({
  recommendation,
}) => {
  const metrics = extractMetrics(recommendation);
  const [copied, setCopied] = useState(false);

  const handleCopyToClipboard = async () => {
    const formattedText = formatProposalRecommendation(recommendation);
    try {
      await navigator.clipboard.writeText(formattedText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy to clipboard:", err);
    }
  };

  const getPriorityColor = (priority: ProposalPriority): string => {
    switch (priority) {
      case "high":
        return "#ef4444";
      case "medium":
        return "#f59e0b";
      case "low":
        return "#10b981";
      default:
        return "#6b7280";
    }
  };

  return (
    <div className="recommendation-results">
      <div className="recommendation-header">
        <h3>Recommendation Generated</h3>
        <button onClick={handleCopyToClipboard} disabled={copied}>
          {copied ? "Copied!" : "Copy to Clipboard"}
        </button>
      </div>

      {/* Metadata */}
      <div className="metadata">
        <div className="metadata-item">
          <strong>DAO:</strong> {recommendation.dao_name}
        </div>
        <div className="metadata-item">
          <strong>Priority:</strong>
          <span
            style={{
              color: getPriorityColor(recommendation.priority),
              fontWeight: "bold",
              textTransform: "uppercase",
            }}
          >
            {recommendation.priority}
          </span>
        </div>
        <div className="metadata-item">
          <strong>Proposals Analyzed:</strong>{" "}
          {recommendation.proposals_analyzed}
        </div>
      </div>

      {/* Title */}
      <div className="recommendation-title">
        <h4>{recommendation.title}</h4>
      </div>

      {/* Content */}
      <div className="recommendation-content">
        <h5>Proposal Content:</h5>
        <div className="content-box">
          <pre>{recommendation.content}</pre>
        </div>
      </div>

      {/* Rationale */}
      <div className="recommendation-rationale">
        <h5>Why This Proposal?</h5>
        <p>{recommendation.rationale}</p>
      </div>

      {/* Impact */}
      <div className="recommendation-impact">
        <h5>Expected Impact:</h5>
        <p>{recommendation.estimated_impact}</p>
      </div>

      {/* Suggested Action */}
      {recommendation.suggested_action && (
        <div className="recommendation-action">
          <h5>Next Steps:</h5>
          <p>{recommendation.suggested_action}</p>
        </div>
      )}

      {/* Token Usage */}
      <div className="token-usage">
        <small>
          Token Usage: {metrics.tokenUsage.breakdown.input_tokens} input +{" "}
          {metrics.tokenUsage.breakdown.output_tokens} output ={" "}
          {metrics.tokenUsage.total} total
        </small>
      </div>
    </div>
  );
};

// ============================================================================
// HOOK FOR API INTEGRATION
// ============================================================================

/**
 * Custom hook for managing proposal recommendation state
 */
export const useProposalRecommendation = (authToken: string) => {
  const [isLoading, setIsLoading] = useState(false);
  const [recommendation, setRecommendation] =
    useState<ProposalRecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generateRecommendation = async (
    request: ProposalRecommendationRequest
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await generateProposalRecommendation(request, authToken);

      if (isProposalRecommendationError(result)) {
        setError(result.error);
        setRecommendation(null);
      } else {
        setRecommendation(result);
        setError(null);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";
      setError(errorMessage);
      setRecommendation(null);
    } finally {
      setIsLoading(false);
    }
  };

  const reset = () => {
    setRecommendation(null);
    setError(null);
  };

  return {
    isLoading,
    recommendation,
    error,
    generateRecommendation,
    reset,
  };
};

// ============================================================================
// EXAMPLE USAGE IN A PAGE COMPONENT
// ============================================================================

export const ProposalRecommendationPage: React.FC = () => {
  const authToken = "your-auth-token-here"; // Get from your auth context/state

  const handleRecommendationGenerated = (
    recommendation: ProposalRecommendationResponse
  ) => {
    console.log("New recommendation generated:", recommendation);
    // You could save to local storage, send analytics, etc.
  };

  return (
    <div className="page">
      <h1>DAO Proposal Recommendations</h1>
      <p>
        Get AI-powered proposal suggestions based on your DAO's mission and
        history.
      </p>

      <ProposalRecommendationForm
        authToken={authToken}
        onRecommendationGenerated={handleRecommendationGenerated}
      />
    </div>
  );
};

export default ProposalRecommendationForm;
