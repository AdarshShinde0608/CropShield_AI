import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import mr from "./locales/mr.json";
import hi from "./locales/hi.json";

const LANGUAGE_KEY = "cropshield.language";
const storedLanguage = localStorage.getItem(LANGUAGE_KEY);
const initialLanguage = storedLanguage === "mr" || storedLanguage === "hi" ? storedLanguage : "en";

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    mr: { translation: mr },
    hi: { translation: hi }
  },
  lng: initialLanguage,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false
});

export default i18n;