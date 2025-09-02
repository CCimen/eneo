import { supportsGpt5Settings } from './supportsGpt5Settings.js';

const unsupportedModels = ["o3-mini-azure", "o3-mini"];

export function supportsTemperature(modelName?: string): boolean {
  if (!modelName) return false;
  
  // GPT-5 and reasoning models don't support temperature
  if (supportsGpt5Settings(modelName)) {
    return false;
  }
  
  // Check other specifically unsupported models
  return !unsupportedModels.includes(modelName);
}
