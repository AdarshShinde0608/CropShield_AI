import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Language } from "../../types/api";

const speechLocales: Record<Language, string> = { en: "en", mr: "mr", hi: "hi" };

export default function ReadAloudButton({
  text,
  language
}: {
  text: string;
  language: Language;
}) {
  const { t } = useTranslation();
  const [message, setMessage] = useState("");
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  const speak = useCallback(() => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      setMessage(t("readAloud.unsupported"));
      return;
    }
    const localePrefix = speechLocales[language].toLowerCase();
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find((candidate) => candidate.lang.toLowerCase().startsWith(localePrefix));
    if (!voice) {
      setMessage(t("readAloud.noVoice", { language: t(`common.${language === "en" ? "english" : language === "mr" ? "marathi" : "hindi"}`) }));
      setSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = voice.lang;
    utterance.voice = voice;
    utterance.onstart = () => {
      setSpeaking(true);
      setMessage("");
    };
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => {
      setSpeaking(false);
      setMessage(t("readAloud.failed"));
    };
    window.speechSynthesis.speak(utterance);
  }, [language, t, text]);

  return (
    <div className="space-y-2">
      <button
        aria-pressed={speaking}
        className="rounded-lg border border-brand-300 bg-white px-4 py-2.5 text-sm font-bold text-brand-900 hover:bg-brand-50"
        onClick={speak}
        type="button"
      >
        {speaking ? t("readAloud.speaking") : t("readAloud.button")}
      </button>
      {message && <p className="text-sm text-slate-600" role="status">{message}</p>}
      <details className="text-sm text-slate-700">
        <summary className="cursor-pointer font-semibold">{t("readAloud.textFallback")}</summary>
        <p className="mt-2 leading-6">{text}</p>
      </details>
    </div>
  );
}
