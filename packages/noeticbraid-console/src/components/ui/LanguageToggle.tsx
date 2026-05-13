import { useTranslation } from 'react-i18next'

import type { SupportedLanguage } from '@/i18n'
import { supportedLanguages } from '@/i18n'

function labelFor(language: SupportedLanguage) {
  return language === 'zh-CN' ? '中' : 'EN'
}

export function LanguageToggle() {
  const { i18n, t } = useTranslation()
  const activeLanguage = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en-US'

  return (
    <div className="language-toggle" role="group" aria-label={t('language.toggleAria')}>
      {supportedLanguages.map((language) => {
        const active = activeLanguage === language
        return (
          <button
            key={language}
            type="button"
            className="language-toggle__button"
            aria-pressed={active}
            aria-label={t('language.current', {
              language: language === 'zh-CN' ? t('language.zh') : t('language.en'),
            })}
            onClick={() => void i18n.changeLanguage(language)}
          >
            {labelFor(language)}
          </button>
        )
      })}
    </div>
  )
}
