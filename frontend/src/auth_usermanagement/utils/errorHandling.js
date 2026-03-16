/**
 * Error handling utilities for auth_usermanagement module
 * 
 * Provides consistent, actionable error messages across all components.
 */

// Common error types and their user-friendly messages
const ERROR_MESSAGES = {
  // Network/connection errors
  NETWORK_ERROR: "Unable to connect to the server. Please check your internet connection and try again.",
  TIMEOUT: "The request timed out. Please try again.",
  
  // Authentication errors
  UNAUTHORIZED: "Your session has expired. Please log in again.",
  FORBIDDEN: "You don't have permission to perform this action.",
  
  // Validation errors
  INVALID_EMAIL: "Please enter a valid email address.",
  DUPLICATE_EMAIL: "This email is already registered.",
  REQUIRED_FIELD: "This field is required.",
  
  // Resource errors
  NOT_FOUND: "The requested resource was not found.",
  ALREADY_EXISTS: "This resource already exists.",
  
  // Server errors
  SERVER_ERROR: "Something went wrong on our end. Please try again later.",
  SERVICE_UNAVAILABLE: "The service is temporarily unavailable. Please try again later.",
  
  // Generic
  UNKNOWN: "An unexpected error occurred. Please try again.",
};

// Error context for specific operations
const OPERATION_CONTEXT = {
  invite_user: {
    action: "inviting user",
    success: "User invited successfully",
    retry: "Please check the email address and try again",
  },
  remove_user: {
    action: "removing user",
    success: "User removed successfully",
    retry: "Please refresh and try again",
  },
  suspend_user: {    action: "suspending user",
    success: "User suspended successfully",
    retry: "Please refresh and try again",
  },
  unsuspend_user: {
    action: "unsuspending user",
    success: "User unsuspended successfully",
    retry: "Please refresh and try again",
  },
  promote_super_admin: {
    action: "granting super admin access",
    success: "User granted super admin access successfully",
    retry: "Please refresh and try again",
  },
  demote_super_admin: {
    action: "removing super admin access",
    success: "User removed from super admin successfully",
    retry: "Please refresh and try again",
  },
  update_role: {
    action: "updating user role",
    success: "User role updated successfully",
    retry: "Please select a valid role and try again",
  },
  load_users: {
    action: "loading users",
    success: "Users loaded successfully",
    retry: "Please try refreshing the page",
  },
  accept_invitation: {
    action: "accepting invitation",
    success: "Invitation accepted successfully",
    retry: "Please check the invitation link and try again",
  },
};

/**
 * Extract error message from various error formats
 */
function extractErrorMessage(error) {
  if (typeof error === 'string') return error;
  
  // FastAPI/backend error format
  if (error?.response?.data?.detail) {
    return error.response.data.detail;
  }
  
  // Axios error
  if (error?.response?.data?.message) {
    return error.response.data.message;
  }
  
  // Network error
  if (error?.message === 'Network Error') {
    return ERROR_MESSAGES.NETWORK_ERROR;
  }
  
  // Timeout
  if (error?.code === 'ECONNABORTED') {
    return ERROR_MESSAGES.TIMEOUT;
  }
  
  // HTTP status codes
  if (error?.response?.status) {
    switch (error.response.status) {
      case 401:
        return ERROR_MESSAGES.UNAUTHORIZED;
      case 403:
        return ERROR_MESSAGES.FORBIDDEN;
      case 404:
        return ERROR_MESSAGES.NOT_FOUND;
      case 409:
        return ERROR_MESSAGES.ALREADY_EXISTS;
      case 500:
        return ERROR_MESSAGES.SERVER_ERROR;
      case 503:
        return ERROR_MESSAGES.SERVICE_UNAVAILABLE;
      default:
        break;
    }
  }
  
  // Generic message
  if (error?.message) {
    return error.message;
  }
  
  return ERROR_MESSAGES.UNKNOWN;
}

/**
 * Get actionable error message with context
 * 
 * @param {string} operation - The operation being performed (e.g., 'invite_user')
 * @param {Error|object|string} error - The error object or message
 * @param {object} context - Additional context (e.g., { email: 'user@example.com' })
 * @returns {string} User-friendly, actionable error message
 */
export function getErrorMessage(operation, error, context = {}) {
  const baseMessage = extractErrorMessage(error);
  const opContext = OPERATION_CONTEXT[operation];
  
  if (!opContext) {
    return baseMessage;
  }
  
  // Build contextual message
  let message = `Error ${opContext.action}`;
  
  // Add specific context
  if (context.email) {
    message += ` for ${context.email}`;
  } else if (context.name) {
    message += ` for ${context.name}`;
  }
  
  message += `: ${baseMessage}`;
  
  // Add retry suggestion
  if (opContext.retry) {
    message += ` ${opContext.retry}`;
  }
  
  return message;
}

/**
 * Get success message for an operation
 */
export function getSuccessMessage(operation, context = {}) {
  const opContext = OPERATION_CONTEXT[operation];
  
  if (!opContext) {
    return "Operation completed successfully";
  }
  
  let message = opContext.success;
  
  // Add specific context
  if (context.email) {
    message = message.replace("User", context.email);
  } else if (context.name) {
    message = message.replace("User", context.name);
  }
  
  return message;
}

/**
 * Check if error is retryable
 */
export function isRetryableError(error) {
  const status = error?.response?.status;
  const message = error?.message;
  
  // Timeout and network errors are retryable
  if (message === 'Network Error' || error?.code === 'ECONNABORTED') {
    return true;
  }
  
  // Server errors (5xx) are retryable
  if (status >= 500 && status < 600) {
    return true;
  }
  
  // Client errors (4xx) are generally not retryable
  // except for 408 (timeout) and 429 (rate limit)
  if (status === 408 || status === 429) {
    return true;
  }
  
  return false;
}

export { ERROR_MESSAGES, OPERATION_CONTEXT };
