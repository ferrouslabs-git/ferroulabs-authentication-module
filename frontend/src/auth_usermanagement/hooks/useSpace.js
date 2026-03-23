import { useAuth } from "./useAuth";

export function useSpace() {
  const { spaces, currentSpaceId, changeSpace } = useAuth();

  const currentSpace = spaces.find((s) => s.id === currentSpaceId) || null;

  return { spaces, space: currentSpace, changeSpace };
}
