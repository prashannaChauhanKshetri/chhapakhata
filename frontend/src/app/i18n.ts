/**
 * Translation layer. Keys are the English text itself (`t('New order')`), so
 * English needs no resource file and a Nepali file can be added later as a
 * plain English → Nepali map in src/locales/ne.json without touching screens.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

void i18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  resources: { en: { translation: {} } },
  keySeparator: false,
  nsSeparator: false,
  returnEmptyString: false,
  interpolation: { escapeValue: false },
});

export default i18n;
