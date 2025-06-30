import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Importing translation files
import translationEN from './locales/en/translation.json';
import translationZH from './locales/zh/translation.json';

const resources = {
  en: {
    translation: translationEN
  },
  zh: {
    translation: translationZH
  }
};

i18n
  .use(LanguageDetector) // Detect user language
  .use(initReactI18next) // Pass i18n instance to react-i18next
  .init({
    resources,
    supportedLngs: ['en', 'zh'],
    fallbackLng: 'en', // use en if detected lng is not available
    lng: 'en', // Default language set to English
    debug: import.meta.env.DEV,
    interpolation: {
      escapeValue: false, // React already safes from xss
    },
    detection: {
      // Order and from where user language should be detected
      order: ['localStorage'], // Only check localStorage, ignore navigator
      // Keys or params to lookup language from
      lookupLocalStorage: 'i18nextLng',
      // Cache user language on
      caches: ['localStorage'],
    }
  });

export default i18n; 