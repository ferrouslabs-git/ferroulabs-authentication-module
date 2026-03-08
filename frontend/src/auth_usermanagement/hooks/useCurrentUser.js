import { useAuth } from "./useAuth";

export function useCurrentUser() {
  const { user, isLoading } = useAuth();
  return { user, isLoading, isPlatformAdmin: Boolean(user?.is_platform_admin) };
}
