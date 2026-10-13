/**
 * classifyError — Converts raw error messages / HTTP statuses into
 * structured, user-friendly error objects.
 *
 * Returns: { message: string, hint: string, retryable: boolean }
 */
export function classifyError(rawMessage = '', httpStatus = null) {
  const msg = rawMessage.toLowerCase();

  // Detect status code from message string if not passed directly
  const statusMatch = msg.match(/http (\d{3})/);
  const status = httpStatus ?? (statusMatch ? parseInt(statusMatch[1]) : null);

  if (status === 429 || msg.includes('rate limit') || msg.includes('429')) {
    return {
      message: 'Rate limited by the pipeline.',
      hint: 'Too many requests. Wait a few seconds and try again.',
      retryable: true,
    };
  }

  if (status === 401 || status === 403) {
    return {
      message: 'Authentication failed.',
      hint: 'Your API key may be missing or expired. Check backend configuration.',
      retryable: false,
    };
  }

  if (status === 502 || status === 503 || status === 504) {
    return {
      message: 'Pipeline is unavailable.',
      hint: 'The backend service is down or overloaded. Try again in a moment.',
      retryable: true,
    };
  }

  if (status === 500) {
    return {
      message: 'Internal pipeline error.',
      hint: 'The verification pipeline encountered an unexpected failure.',
      retryable: true,
    };
  }

  if (msg.includes('timed out') || msg.includes('timeout') || msg.includes('120 seconds')) {
    return {
      message: 'Verification timed out.',
      hint: 'The pipeline took longer than 120 s. The agents may be under heavy load.',
      retryable: true,
    };
  }

  if (msg.includes('network') || msg.includes('fetch') || msg.includes('failed to fetch')) {
    return {
      message: 'Network connection lost.',
      hint: 'Check your internet connection and that the backend server is running.',
      retryable: true,
    };
  }

  if (msg.includes('evaluation failure') || msg.includes('encountered a failure')) {
    return {
      message: 'Pipeline evaluation failed.',
      hint: 'The judge agent could not reach a verdict. Try rephrasing the claim.',
      retryable: true,
    };
  }

  // Fallback
  return {
    message: rawMessage || 'An unexpected error occurred.',
    hint: null,
    retryable: true,
  };
}
