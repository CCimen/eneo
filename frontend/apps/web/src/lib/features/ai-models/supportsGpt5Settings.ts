const gpt5Models = ["gpt-5", "gpt-5-mini", "gpt-5-nano", "o3", "o4"];

export function supportsGpt5Settings(modelName?: string): boolean {
  if (!modelName) return false;
  
  const lowerName = modelName.toLowerCase();
  
  // Check for exact starts with patterns
  if (gpt5Models.some(model => lowerName.startsWith(model))) {
    return true;
  }
  
  // Check for reasoning model patterns
  if (lowerName.includes("reasoning") || lowerName.includes("gpt5") || lowerName.includes("gpt-5")) {
    return true;
  }
  
  return false;
}

export function isResponsesApi(apiType?: string | null, modelName?: string): boolean {
  return apiType === "responses" || (apiType === null && supportsGpt5Settings(modelName));
}