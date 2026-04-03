export const SPLASH_TO_MODULE = {
  S1: "module_a",
  S2: "module_a",
  S3: "module_b",
  S4: "module_b",
  S5: "module_c",
  S6: "module_c",
  S7: "module_d",
  S8: "module_d",
};

export const SPLASH_IDS = Object.keys(SPLASH_TO_MODULE);

export function getModuleForSplash(splashId) {
  return SPLASH_TO_MODULE[splashId] || null;
}
