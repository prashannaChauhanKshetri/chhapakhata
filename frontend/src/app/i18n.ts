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
  resources: {
    en: {
      // English text is the key; only singular forms of counted messages are listed.
      translation: {
        '{{count}} customers · {{amount}} over 90 days_one':
          '{{count}} customer · {{amount}} over 90 days',
        '{{count}} invoices_one': '{{count}} invoice',
        '{{count}} items_one': '{{count}} item',
        '{{count}} jobs_one': '{{count}} job',
        '{{count}} payments_one': '{{count}} payment',
      },
    },
  },
  keySeparator: false,
  nsSeparator: false,
  returnEmptyString: false,
  showSupportNotice: false,
  interpolation: { escapeValue: false },
});

export default i18n;
