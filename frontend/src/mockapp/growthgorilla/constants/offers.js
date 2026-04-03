export const OFFERS = [
  { code: "ONE_MONTH_FREE", label: "1 month free" },
  { code: "TWENTY_DOLLARS_OFF", label: "$20 off" },
  { code: "TWENTY_PERCENT_OFF_FULL", label: "20% off full modules" },
];

export function pickRandomOffer() {
  const index = Math.floor(Math.random() * OFFERS.length);
  return OFFERS[index];
}
