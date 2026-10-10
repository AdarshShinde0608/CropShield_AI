import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren
} from "react";
import { useTranslation } from "react-i18next";
import * as authApi from "../api/auth";
import { AUTH_TOKEN_KEY } from "../api/client";
import type { Language, LoginRequest, ProfileUpdateRequest, RegisterRequest, User } from "../types/api";

const LANGUAGE_KEY = "cropshield.language";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (request: LoginRequest) => Promise<void>;
  register: (request: RegisterRequest) => Promise<void>;
  logout: () => void;
  changeLanguage: (language: Language) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const { i18n } = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(() => Boolean(localStorage.getItem(AUTH_TOKEN_KEY)));

  useEffect(() => {
    let active = true;
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) return () => { active = false; };

    authApi.getCurrentUser()
      .then((currentUser) => {
        if (active) {
          setUser(currentUser);
          localStorage.setItem(LANGUAGE_KEY, currentUser.language);
          void i18n.changeLanguage(currentUser.language);
        }
      })
      .catch(() => {
        if (active) {
          localStorage.removeItem(AUTH_TOKEN_KEY);
          setUser(null);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => { active = false; };
  }, [i18n]);

  const acceptTokenResponse = useCallback(async (response: { access_token: string; user: User }) => {
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    localStorage.setItem(LANGUAGE_KEY, response.user.language);
    setUser(response.user);
    await i18n.changeLanguage(response.user.language);
  }, [i18n]);

  const login = useCallback(async (request: LoginRequest) => {
    await acceptTokenResponse(await authApi.login(request));
  }, [acceptTokenResponse]);

  const register = useCallback(async (request: RegisterRequest) => {
    await acceptTokenResponse(await authApi.register(request));
  }, [acceptTokenResponse]);

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setUser(null);
    window.location.replace("/login");
  }, []);

  const changeLanguage = useCallback(async (language: Language) => {
    const previousLanguage = i18n.resolvedLanguage;
    localStorage.setItem(LANGUAGE_KEY, language);
    await i18n.changeLanguage(language);
    if (!user) return;
    try {
      const updatedUser = await authApi.updateProfile({ language } satisfies ProfileUpdateRequest);
      setUser(updatedUser);
    } catch (error) {
      const rollbackLanguage = previousLanguage === "mr" || previousLanguage === "hi" ? previousLanguage : "en";
      localStorage.setItem(LANGUAGE_KEY, rollbackLanguage);
      await i18n.changeLanguage(rollbackLanguage);
      throw error;
    }
  }, [i18n, user]);

  const value = useMemo(
    () => ({ user, isLoading, login, register, logout, changeLanguage }),
    [user, isLoading, login, register, logout, changeLanguage]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}