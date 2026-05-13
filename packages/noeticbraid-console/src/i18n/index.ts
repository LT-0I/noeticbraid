import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import enUS from './locales/en-US.json'
import zhCN from './locales/zh-CN.json'

export const supportedLanguages = ['zh-CN', 'en-US'] as const
export type SupportedLanguage = (typeof supportedLanguages)[number]

const storageKey = 'noeticbraid.locale'

function isSupportedLanguage(value: string | null | undefined): value is SupportedLanguage {
  return value === 'zh-CN' || value === 'en-US'
}

export function detectInitialLanguage(): SupportedLanguage {
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem(storageKey)
    if (isSupportedLanguage(stored)) return stored
  }

  if (typeof navigator !== 'undefined' && navigator.language.toLowerCase().startsWith('zh')) {
    return 'zh-CN'
  }

  return 'en-US'
}

function applyDocumentLanguage(language: string) {
  if (typeof document === 'undefined') return
  const normalized = isSupportedLanguage(language) ? language : 'en-US'
  document.documentElement.lang = normalized
  document.documentElement.dataset.theme = 'light'
}

void i18n.use(initReactI18next).init({
  resources: {
    'zh-CN': { translation: zhCN },
    'en-US': { translation: enUS },
  },
  lng: detectInitialLanguage(),
  fallbackLng: 'en-US',
  supportedLngs: supportedLanguages,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
})

applyDocumentLanguage(i18n.language)

i18n.on('languageChanged', (language) => {
  applyDocumentLanguage(language)
  if (typeof window !== 'undefined' && isSupportedLanguage(language)) {
    window.localStorage.setItem(storageKey, language)
  }
})

export { storageKey as localeStorageKey }
export default i18n
